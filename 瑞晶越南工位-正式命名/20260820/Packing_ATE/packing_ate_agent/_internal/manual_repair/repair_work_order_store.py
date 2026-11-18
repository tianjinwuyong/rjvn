# -*- coding: utf-8 -*-
"""Small append-only local cache used by the shared repair panel."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path


def _db_path(station_code: str) -> Path:
    base = Path(os.environ.get("STATION_DATA_DIR", Path.cwd() / "data"))
    base.mkdir(parents=True, exist_ok=True)
    return base / f"repair_work_orders_{str(station_code).strip().lower()}.sqlite"


def init_store(station_code: str) -> None:
    with sqlite3.connect(str(_db_path(station_code))) as db:
        db.execute("CREATE TABLE IF NOT EXISTS work_orders (station_code TEXT NOT NULL, work_order_id TEXT NOT NULL, payload_json TEXT NOT NULL, updated_at INTEGER NOT NULL, PRIMARY KEY(station_code, work_order_id))")
        db.commit()


def upsert_work_order(station_code: str, row: dict) -> None:
    init_store(station_code)
    work_order_id = str(row.get("workOrderNo") or row.get("work_order_id") or row.get("id") or "").strip()
    if not work_order_id:
        return
    import time
    with sqlite3.connect(str(_db_path(station_code))) as db:
        db.execute("INSERT OR REPLACE INTO work_orders(station_code, work_order_id, payload_json, updated_at) VALUES(?,?,?,?)", (str(station_code), work_order_id, json.dumps(row, ensure_ascii=False), int(time.time())))
        db.commit()


def latest_work_orders(station_code: str, limit: int = 10) -> list:
    init_store(station_code)
    with sqlite3.connect(str(_db_path(station_code))) as db:
        rows = db.execute("SELECT payload_json FROM work_orders WHERE station_code=? ORDER BY updated_at DESC LIMIT ?", (str(station_code), int(limit))).fetchall()
    result = []
    for (payload,) in rows:
        try:
            result.append(json.loads(payload))
        except Exception:
            continue
    return result
