# -*- coding: utf-8 -*-
"""Shared automatic-line retest authorization.

A repeated SN is blocked unless the operator explicitly arms one retest.
The authorization is single-use. Every action and result is append-only.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from station_domain import LINE_CODE

APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
STATE_DB = APP_DIR / "station_retest_history.db"
_LOCK = threading.RLock()


def _now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect():
    db = sqlite3.connect(STATE_DB, timeout=10)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS retest_authorizations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_code TEXT NOT NULL,
        target_sn TEXT NOT NULL DEFAULT '',
        actor TEXT NOT NULL,
        reason TEXT NOT NULL DEFAULT '',
        armed_at TEXT NOT NULL,
        consumed_at TEXT,
        consumed_sn TEXT,
        result TEXT,
        state TEXT NOT NULL DEFAULT 'ARMED')""")
        db.execute("""CREATE TABLE IF NOT EXISTS retest_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_code TEXT NOT NULL,
        line_code TEXT NOT NULL DEFAULT 'AUTO-LINE',
        sn TEXT NOT NULL DEFAULT '',
        action TEXT NOT NULL,
        result TEXT NOT NULL DEFAULT '',
        actor TEXT NOT NULL DEFAULT 'OPERATOR',
        detail_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL)""")
        existing = {row[1] for row in db.execute("PRAGMA table_info(retest_history)")}
        if "line_code" not in existing:
            db.execute(
                "ALTER TABLE retest_history ADD COLUMN line_code "
                "TEXT NOT NULL DEFAULT 'AUTO-LINE'")
        db.execute("""CREATE TABLE IF NOT EXISTS retest_mode(
        station_code TEXT PRIMARY KEY,
        enabled INTEGER NOT NULL DEFAULT 0,
        changed_at TEXT NOT NULL,
        changed_by TEXT NOT NULL)""")
        yield db
        db.commit()
    finally:
        db.close()


def _history(db, station_code, sn, action, result="", actor="OPERATOR", detail=None):
    db.execute(
        """INSERT INTO retest_history
           (station_code,line_code,sn,action,result,actor,detail_json,created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (station_code, LINE_CODE, sn or "", action, str(result or "").upper(), actor,
         json.dumps(detail or {}, ensure_ascii=False), _now()),
    )


def arm_retest(station_code, sn="", actor="OPERATOR", reason="OPERATOR_CONFIRMED"):
    """Arm exactly one repeated-SN attempt for this station."""
    with _LOCK, _connect() as db:
        db.execute(
            "UPDATE retest_authorizations SET state='CANCELLED' "
            "WHERE station_code=? AND state='ARMED'",
            (station_code,),
        )
        cur = db.execute(
            """INSERT INTO retest_authorizations
               (station_code,target_sn,actor,reason,armed_at,state)
               VALUES(?,?,?,?,?,'ARMED')""",
            (station_code, (sn or "").strip(), actor, reason, _now()),
        )
        _history(db, station_code, sn, "RETEST_ARMED", actor=actor,
                 detail={"authorizationId": cur.lastrowid, "singleUse": True})
        return cur.lastrowid


def cancel_retest(station_code, actor="OPERATOR"):
    with _LOCK, _connect() as db:
        changed = db.execute(
            "UPDATE retest_authorizations SET state='CANCELLED' "
            "WHERE station_code=? AND state='ARMED'",
            (station_code,),
        ).rowcount
        if changed:
            _history(db, station_code, "", "RETEST_CANCELLED", actor=actor)
        return bool(changed)


def retest_is_armed(station_code):
    with _LOCK, _connect() as db:
        return bool(db.execute(
            "SELECT 1 FROM retest_authorizations "
            "WHERE station_code=? AND state='ARMED' ORDER BY id DESC LIMIT 1",
            (station_code,),
        ).fetchone())


def claim_duplicate_retest(station_code, sn):
    """Consume a matching one-shot authorization for a duplicate scan."""
    normalized = (sn or "").strip()
    if not normalized:
        return False
    with _LOCK, _connect() as db:
        row = db.execute(
            """SELECT id,target_sn,actor FROM retest_authorizations
               WHERE station_code=? AND state='ARMED'
                 AND (target_sn='' OR UPPER(target_sn)=UPPER(?))
               ORDER BY id DESC LIMIT 1""",
            (station_code, normalized),
        ).fetchone()
        if not row:
            return False
        db.execute(
            """UPDATE retest_authorizations
               SET state='CONSUMED',consumed_at=?,consumed_sn=?
               WHERE id=? AND state='ARMED'""",
            (_now(), normalized, row[0]),
        )
        _history(db, station_code, normalized, "RETEST_AUTHORIZED",
                 actor=row[2], detail={"authorizationId": row[0]})
        return True


def consume_retest_result(station_code, sn, result, detail=None):
    """Consume authorization during file/database ingestion and keep the result."""
    normalized = (sn or "").strip()
    with _LOCK:
        accepted = claim_duplicate_retest(station_code, normalized)
        if accepted:
            with _connect() as db:
                db.execute(
                    """UPDATE retest_authorizations SET result=?
                       WHERE id=(SELECT id FROM retest_authorizations
                       WHERE station_code=? AND consumed_sn=?
                       ORDER BY id DESC LIMIT 1)""",
                    (str(result or "").upper(), station_code, normalized),
                )
                _history(db, station_code, normalized, "RETEST_RESULT",
                         result=result, detail=detail)
        return accepted


def is_unlimited_retest(station_code):
    with _LOCK, _connect() as db:
        row = db.execute(
            "SELECT enabled FROM retest_mode WHERE station_code=?",
            (station_code,),
        ).fetchone()
        return bool(row and row[0])


def set_unlimited_retest(station_code, enabled, mes_base_url="", actor="OPERATOR"):
    with _LOCK, _connect() as db:
        db.execute(
            """INSERT INTO retest_mode(station_code,enabled,changed_at,changed_by)
               VALUES(?,?,?,?) ON CONFLICT(station_code) DO UPDATE SET
               enabled=excluded.enabled,changed_at=excluded.changed_at,
               changed_by=excluded.changed_by""",
            (station_code, int(bool(enabled)), _now(), actor),
        )
        _history(db, station_code, "", "UNLIMITED_MODE_CHANGED",
                 actor=actor, detail={"enabled": bool(enabled)})
    return bool(enabled)


def append_history(station_code, action, sn="", batch_id="", result="",
                   attempt_no=None, actor="OPERATOR", detail=None):
    with _LOCK, _connect() as db:
        payload = dict(detail or {})
        payload.update({"batchId": batch_id, "attemptNo": attempt_no})
        _history(db, station_code, sn, action, result, actor, payload)


class RetestController:
    def __init__(self, station_code, mes_base_url=""):
        self.station_code = station_code
        self.mes_base_url = mes_base_url

    @property
    def unlimited(self):
        return is_unlimited_retest(self.station_code)

    def arm(self, sn="", actor="OPERATOR", permission_reason="OPERATOR_CONFIRMED", **_):
        token = arm_retest(self.station_code, sn, actor, permission_reason)
        return True, {"ok": True, "authorizationId": token, "singleUse": True}


def install_station_retest_panel(root, station_code, mes_base_url="",
                                 test_station=True, announcer=None, host=None):
    """Add a persistent one-shot Confirm Retest button to a Tk agent."""
    if os.environ.get("STATION_MINIMAL_UI", "0") == "1":
        return None
    import tkinter as tk

    text = tk.StringVar()

    def paint():
        armed = retest_is_armed(station_code)
        text.set("复测已确认：等待下一条重复SN" if armed else "确认复测")
        button.configure(bg="#16a34a" if armed else "#9a3412")

    def click():
        if retest_is_armed(station_code):
            cancel_retest(station_code)
            if announcer:
                announcer("复测授权已取消")
        else:
            arm_retest(station_code)
            if announcer:
                announcer("复测已确认")
        paint()

    button_parent = host or getattr(root, "_retest_host", None) or root
    button = tk.Button(
        button_parent, textvariable=text, command=click, fg="white",
        font=("Microsoft YaHei UI", 11, "bold"), padx=12, pady=6,
    )
    if host is not None or getattr(root, "_retest_host", None) is not None:
        button.pack(side=tk.LEFT, padx=12, pady=6)
    else:
        # Backward-compatible fallback for stations without a dedicated action row.
        button.place(relx=1.0, x=-12, y=12, anchor="ne")
        button.lift()
    paint()
    return button


def render_streamlit_retest(st, station_code, mes_base_url="", test_station=True):
    armed = retest_is_armed(station_code)
    label = "取消复测授权" if armed else "确认复测"
    if st.button(label, key=f"retest_{station_code}", use_container_width=True):
        cancel_retest(station_code) if armed else arm_retest(station_code)
        st.rerun()
    st.caption("已授权下一次重复SN复测" if armed else "重复SN默认拦截；复测前必须确认")


def install_qt_retest_button(parent, layout, station_code, announcer=None):
    """Add the same one-shot control to a PySide/PyQt toolbar."""
    try:
        from PySide6.QtWidgets import QPushButton
    except ImportError:
        from PySide2.QtWidgets import QPushButton
    button = QPushButton(parent)
    button.setToolTip("仅授权下一次重复SN复测；使用后自动恢复重码拦截")

    def paint():
        armed = retest_is_armed(station_code)
        button.setText("复测已确认：等待重复SN" if armed else "确认复测")
        color = "#16a34a" if armed else "#9a3412"
        button.setStyleSheet(
            f"QPushButton{{background:{color};color:white;font-weight:700;padding:7px 12px;}}"
        )

    def click():
        if retest_is_armed(station_code):
            cancel_retest(station_code)
            if announcer:
                announcer("复测授权已取消")
        else:
            arm_retest(station_code)
            if announcer:
                announcer("复测已确认")
        paint()

    button.clicked.connect(click)
    layout.addWidget(button)
    paint()
    return button
