# -*- coding: utf-8 -*-
"""Mandatory contract for decoupled manual-line station cores.

The Core owns production state. 2D and 3D are peer views and must never import
or launch one another. Production records flow local -> MES; MES may only send
control/reference data such as active WO and append-only confirmed NG records.
"""
from __future__ import annotations

import json
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path


class StationCoreContract(ABC):
    station_code = ""
    schema_version = "1"

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.init_contract_tables()

    def connect(self):
        db=sqlite3.connect(str(self.db_path),timeout=30);db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON");db.execute("PRAGMA journal_mode=WAL");return db

    def init_contract_tables(self):
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS core_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS software_change_log(
              change_key TEXT PRIMARY KEY,version TEXT NOT NULL,component TEXT NOT NULL,
              reason TEXT NOT NULL,summary TEXT NOT NULL,verification TEXT NOT NULL,changed_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS mes_outbox(
              id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL UNIQUE,payload TEXT NOT NULL,
              created_at INTEGER NOT NULL,sent_at INTEGER,attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT '');
            CREATE TRIGGER IF NOT EXISTS protect_change_log_update BEFORE UPDATE ON software_change_log
              BEGIN SELECT RAISE(ABORT,'software_change_log is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS protect_change_log_delete BEFORE DELETE ON software_change_log
              BEGIN SELECT RAISE(ABORT,'software_change_log is append-only'); END;
            """)
            db.execute("INSERT OR IGNORE INTO core_metadata(key,value) VALUES('station_code',?)",(self.station_code,))
            db.execute("INSERT OR IGNORE INTO core_metadata(key,value) VALUES('schema_version',?)",(self.schema_version,))

    def record_change(self,change_key,version,component,reason,summary,verification):
        if not all(str(x).strip() for x in (change_key,version,component,reason,summary,verification)):
            raise ValueError("change record requires key, version, component, reason, summary and verification")
        with self.connect() as db:db.execute("INSERT INTO software_change_log VALUES(?,?,?,?,?,?,?)",(change_key,version,component,reason,summary,verification,time.strftime('%Y-%m-%d %H:%M:%S')))

    def queue_mes(self,event_id,payload):
        with self.connect() as db:db.execute("INSERT OR IGNORE INTO mes_outbox(event_id,payload,created_at) VALUES(?,?,?)",(event_id,json.dumps(payload,ensure_ascii=False),int(time.time())))

    @abstractmethod
    def snapshot(self):
        """Return the production projection consumed identically by 2D and 3D."""

    @abstractmethod
    def resource_tables(self,limit=500):
        """Return LIVE/SN/NG/RAW/COMMS/SETTINGS/CHANGE LOG resources."""

    @abstractmethod
    def sync_once(self):
        """Send local outbox records to MES without modifying production evidence."""


