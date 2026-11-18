"""Non-blocking first-install resource reader for legacy auto-line agents."""
import json
import sqlite3
import threading
import time
from pathlib import Path


SKIP_DIRS = {
    "build", "dist", "_internal", "__pycache__", ".git", ".venv",
    "node_modules", "$recycle.bin",
}


def _read(station_dir):
    try:
        from station_resource_viewer import read_tabular_resource
        station_dir = Path(station_dir)
        db_path = station_dir / "data" / "common_agent.sqlite"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(db_path)) as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS local_resource_reads(
              read_id INTEGER PRIMARY KEY AUTOINCREMENT, resource_path TEXT NOT NULL,
              resource_type TEXT NOT NULL, fingerprint TEXT NOT NULL, bytes INTEGER NOT NULL DEFAULT 0,
              modified_ns INTEGER NOT NULL DEFAULT 0, columns_json TEXT NOT NULL DEFAULT '[]',
              rows_json TEXT NOT NULL DEFAULT '[]', row_count INTEGER NOT NULL DEFAULT 0,
              read_at INTEGER NOT NULL, read_error TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS runtime_state(
              state_key TEXT PRIMARY KEY, state_value TEXT NOT NULL, updated_at INTEGER NOT NULL
            );
            """)
            marker = db.execute("SELECT state_value FROM runtime_state WHERE state_key=?",
                                ("local_resources.initial_read.v1",)).fetchone()
            if marker and marker[0] == "complete":
                return
        supported = {".csv", ".xlsx", ".xlsm", ".json", ".html", ".htm"}
        resources = []
        for path in station_dir.rglob("*"):
            if ({part.lower() for part in path.relative_to(station_dir).parts[:-1]} & SKIP_DIRS):
                continue
            if path.is_file() and path.suffix.lower() in supported and not path.name.startswith("~$"):
                stat = path.stat()
                if stat.st_size > 50 * 1024 * 1024:
                    continue
                resources.append({"path": str(path), "extension": path.suffix.lower(),
                                  "bytes": stat.st_size, "modified_ns": stat.st_mtime_ns})
        with sqlite3.connect(str(db_path)) as db:
            for item in resources:
                path = str(item.get("path", "")); table = {}
                if item["extension"] == ".json":
                    try:
                        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
                        records = payload if isinstance(payload, list) else [payload]
                        records = [row if isinstance(row, dict) else {"value": row} for row in records]
                        columns = list(dict.fromkeys(key for row in records for key in row))
                        table = {"columns": columns, "rows": records}
                    except Exception as exc:
                        table = {"columns": [], "rows": [], "error": str(exc)}
                else:
                    table = read_tabular_resource(path, limit=10000)
                rows = table.get("rows", [])
                db.execute(
                    "INSERT INTO local_resource_reads "
                    "(resource_path,resource_type,fingerprint,bytes,modified_ns,columns_json,rows_json,row_count,read_at,read_error) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (path, str(item.get("extension", "")).upper().lstrip("."),
                     str(item.get("modified_ns", "")), int(item.get("bytes", 0) or 0),
                     int(item.get("modified_ns", 0) or 0),
                     json.dumps(table.get("columns", []), ensure_ascii=False),
                     json.dumps(rows, ensure_ascii=False, default=str), len(rows),
                     int(time.time() * 1000), str(table.get("error", ""))),
                )
            db.execute("INSERT OR REPLACE INTO runtime_state VALUES(?,?,?)",
                       ("local_resources.initial_read.v1", "complete", int(time.time() * 1000)))
            db.commit()
    except Exception:
        # Resource discovery must never prevent a station from starting.
        return


def start_first_install_resource_read(station_dir):
    threading.Thread(target=_read, args=(station_dir,),
                     name="initial-resource-read", daemon=True).start()
