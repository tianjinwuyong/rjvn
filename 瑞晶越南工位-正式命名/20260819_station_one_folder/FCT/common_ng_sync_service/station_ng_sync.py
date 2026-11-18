# -*- coding: utf-8 -*-
"""Shared background MES confirmed-NG synchronizer for every station agent."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import urllib.request
from pathlib import Path


class NgBroadcastSync:
    """Poll MES off the UI thread and maintain a local confirmed-NG cache."""

    def __init__(self, db_path, mes_url="", interval_seconds=5):
        self.db_path = Path(db_path)
        self.mes_url = (mes_url or "http://192.168.6.155:8080/api/pda/events").rstrip("/")
        self.interval_seconds = max(2, int(interval_seconds))
        self._stop = threading.Event()
        self._thread = None
        self._last_error = ""
        self._init_db()

    def _snapshot_url(self):
        base = self.mes_url
        if "/api/" in base:
            base = base.split("/api/", 1)[0]
        return base + "/api/station/bucket-snapshots"

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path), timeout=10) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS mes_ng_cache(
                sn TEXT PRIMARY KEY, source_station TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '', snapshot_version INTEGER NOT NULL DEFAULT 0,
                received_at INTEGER NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS mes_ng_sync_state(
                id INTEGER PRIMARY KEY CHECK(id=1), last_success_at INTEGER,
                last_error TEXT NOT NULL DEFAULT '', snapshot_version INTEGER NOT NULL DEFAULT 0)""")
            db.execute("INSERT OR IGNORE INTO mes_ng_sync_state(id) VALUES(1)")

    def refresh_once(self):
        with urllib.request.urlopen(self._snapshot_url(), timeout=3) as response:
            raw = json.loads(response.read().decode("utf-8") or "{}")
        snapshots = raw.get("items") or (raw.get("data") or {}).get("items") or []
        active = {}
        version = 0
        for bucket in snapshots:
            if str(bucket.get("bucketName") or "").lower() != "confirmed_ng":
                continue
            version = max(version, int(bucket.get("version") or 0))
            source = str(bucket.get("stationCode") or "")
            for item in bucket.get("payload") or []:
                sn = str(item.get("sn") or item.get("productSn") or "").strip().upper()
                if sn:
                    active[sn] = (source, str(item.get("reason") or item.get("errorCode") or "MES CONFIRMED NG"))
        now = int(time.time() * 1000)
        with sqlite3.connect(str(self.db_path), timeout=10) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM mes_ng_cache")
            db.executemany(
                "INSERT INTO mes_ng_cache(sn,source_station,reason,snapshot_version,received_at) VALUES(?,?,?,?,?)",
                [(sn, source, reason, version, now) for sn, (source, reason) in active.items()],
            )
            db.execute("UPDATE mes_ng_sync_state SET last_success_at=?,last_error='',snapshot_version=? WHERE id=1", (now, version))
        self._last_error = ""
        return len(active)

    def lookup(self, sn):
        code = str(sn or "").strip().upper()
        with sqlite3.connect(str(self.db_path), timeout=3) as db:
            return db.execute("SELECT source_station,reason,received_at FROM mes_ng_cache WHERE sn=?", (code,)).fetchone()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        def run():
            while not self._stop.is_set():
                try:
                    self.refresh_once()
                except Exception as exc:
                    self._last_error = str(exc)
                    with sqlite3.connect(str(self.db_path), timeout=3) as db:
                        db.execute("UPDATE mes_ng_sync_state SET last_error=? WHERE id=1", (self._last_error[:500],))
                self._stop.wait(self.interval_seconds)
        self._thread = threading.Thread(target=run, name="mes-confirmed-ng-sync", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

