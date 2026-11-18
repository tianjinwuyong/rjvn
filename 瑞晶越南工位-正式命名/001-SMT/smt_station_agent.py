# -*- coding: utf-8 -*-
"""Canonical SMT L001 station runtime.

Station owns raw evidence and a durable outbox. MES owns canonical SN/NG/route
state. Scanner input is guard-only and never registers a production SN.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import socket
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

DOMAIN = "smt"
LINE_CODE = "L001"
DEFAULT_MES = os.getenv("RUIJING_MES_URL", "http://192.168.6.155:8080/api").rstrip("/")
RESULT_ALIASES = {
    "PASS": "PASS", "OK": "PASS", "GOOD": "PASS", "1": "PASS", "TRUE": "PASS",
    "NG": "NG", "FAIL": "NG", "FAILED": "NG", "NOK": "NG", "BAD": "NG", "0": "NG", "FALSE": "NG",
}
COMMON_RESPONSIBILITIES = [
    "ENDPOINT_IDENTITY", "HEARTBEAT", "STATION_STATE", "WIP_TRACKING",
    "ROUTE_STATUS_VALIDATION", "RECIPE_VISIBILITY", "FAULT_LIFECYCLE",
    "RAW_EVIDENCE", "OFFLINE_ORDERED_REPLAY",
]
STATION_RESPONSIBILITIES = {
    "smt_pda_loading": [
        "MATERIAL_ID_CAPTURE", "WORK_ORDER_BINDING", "OPERATOR_TRACE",
        "MACHINE_SLOT_FEEDER_REEL_POKA_YOKE", "LOT_EXPIRY_GUARD",
        "LINE_LEADER_RELEASE", "REMAINING_MATERIAL_TRACE", "ROLL_CHANGE_TRACE",
    ],
    "smt_laser_marking": ["UNIT_INITIALIZATION", "UNIT_PERSONALIZATION", "MARK_RESULT"],
    "smt_auto_insertion": ["MATERIAL_TRACE", "TOOL_TRACE", "ACTIVITY_TRACE", "INSERTION_RESULT"],
    "smt_printer": ["SOLDER_PASTE_PRINT_RESULT", "STENCIL_TRACE", "STENCIL_CLEANING", "PASTE_MATERIAL_TRACE"],
    "smt_spi": ["SOLDER_PASTE_INSPECTION", "MEASUREMENT_TRACE", "DEFECT_TRACE"],
    "smt_placement": ["EXACT_MATERIAL_TRACE", "FEEDER_TRACE", "TOOL_TRACE", "PLACEMENT_CYCLE_TRACE", "FAILED_PICKUP_TRACE"],
    "smt_aoi": ["AUTOMATED_OPTICAL_INSPECTION", "COMPONENT_OFFSET_MEASUREMENT", "DEFECT_TRACE"],
}


def now_ms():
    return int(time.time() * 1000)


def local_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("192.168.6.155", 8080))
        value = sock.getsockname()[0]
        sock.close()
        return value
    except OSError:
        return ""


class SingleInstance:
    def __init__(self, name, directory):
        self.path = Path(directory) / f".{name}.lock"
        self.handle = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.path, "a+", encoding="ascii")
        try:
            import msvcrt
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
        except (ImportError, OSError):
            self.handle.close()
            self.handle = None
            raise RuntimeError("This station agent is already running.")
        return self

    def close(self):
        if not self.handle:
            return
        try:
            import msvcrt
            self.handle.seek(0)
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        self.handle.close()
        self.handle = None


class SmtStationAgent:
    def __init__(self, config_path):
        self.config_path = Path(config_path).resolve()
        self.cfg = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
        self.code = str(self.cfg["stationCode"]).strip().lower()
        if self.cfg.get("domain") != DOMAIN or self.cfg.get("lineCode") != LINE_CODE:
            raise ValueError("Configuration must use SMT domain and L001 line.")
        if not self.code.startswith("smt_"):
            raise ValueError("SMT stationCode must start with smt_.")
        self.station_dir = self.config_path.parent
        self.db_path = self.station_dir / "smt_station_cache.db"
        self.mes_url = str(self.cfg.get("mesUrl") or DEFAULT_MES).rstrip("/")
        self.events_url = self.mes_url + "/pda/events"
        self.station_ip = str(self.cfg.get("stationIp") or "").strip()
        self.stop_event = threading.Event()
        self.online = False
        self.last_message = ""
        self._init_db()

    def connect(self):
        db = sqlite3.connect(str(self.db_path), timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _init_db(self):
        with self.connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS mes_outbox(
                  id INTEGER PRIMARY KEY,
                  event_id TEXT NOT NULL UNIQUE,
                  event_type TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  sent_at INTEGER,
                  attempts INTEGER NOT NULL DEFAULT 0,
                  last_error TEXT,
                  delivery_status TEXT NOT NULL DEFAULT 'PENDING'
                );
                CREATE INDEX IF NOT EXISTS idx_smt_outbox_pending
                  ON mes_outbox(sent_at, id);
                CREATE TABLE IF NOT EXISTS raw_records(
                  id INTEGER PRIMARY KEY,
                  source_key TEXT NOT NULL UNIQUE,
                  source_ref TEXT NOT NULL,
                  sn TEXT,
                  result TEXT,
                  raw_json TEXT NOT NULL,
                  captured_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scan_audit(
                  id INTEGER PRIMARY KEY,
                  sn TEXT NOT NULL,
                  decision TEXT NOT NULL,
                  detail TEXT,
                  scanned_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runtime_state(
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL,
                  updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS station_activity(
                  id INTEGER PRIMARY KEY,
                  event_id TEXT NOT NULL UNIQUE,
                  activity_type TEXT NOT NULL,
                  sn TEXT,
                  detail_json TEXT NOT NULL,
                  occurred_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS active_faults(
                  fault_code TEXT PRIMARY KEY,
                  severity TEXT NOT NULL,
                  message TEXT NOT NULL,
                  occurred_at INTEGER NOT NULL,
                  acknowledged_at INTEGER,
                  cleared_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS pda_loading_state(
                  key TEXT PRIMARY KEY,
                  value_json TEXT NOT NULL,
                  updated_at INTEGER NOT NULL
                );
                """
            )
            columns = {row[1] for row in db.execute("PRAGMA table_info(mes_outbox)")}
            if "delivery_status" not in columns:
                db.execute(
                    "ALTER TABLE mes_outbox ADD COLUMN delivery_status TEXT NOT NULL DEFAULT 'PENDING'"
                )

    def station_ip_value(self):
        # SMT addresses are intentionally pending until commissioning.  Do not
        # substitute the MES host/local NIC address, because MES correctly
        # treats that as an identity mismatch.
        return self.station_ip or None

    def envelope(self, event_type, payload):
        stamp = now_ms()
        event_id = f"{self.code}-{stamp}-{uuid.uuid4().hex[:10]}"
        common = {
            "eventId": event_id,
            "stationCode": self.code,
            "stationIp": self.station_ip_value(),
            "domain": DOMAIN,
            "lineCode": LINE_CODE,
            "sequence": int(self.cfg["sequence"]),
            "timestamp": stamp,
        }
        return event_id, {
            "type": event_type,
            "stationCode": self.code,
            "domain": DOMAIN,
            "lineCode": LINE_CODE,
            "payload": {**payload, **common},
        }

    def queue(self, event_type, payload, flush=True):
        event_id, body = self.envelope(event_type, payload)
        with self.connect() as db:
            db.execute(
                """INSERT OR IGNORE INTO mes_outbox
                   (event_id,event_type,payload_json,created_at)
                   VALUES(?,?,?,?)""",
                (event_id, event_type, json.dumps(body, ensure_ascii=False), now_ms()),
            )
        if flush:
            self.flush()
        return event_id

    def flush(self, limit=100):
        sent = 0
        with self.connect() as db:
            rows = db.execute(
                """SELECT id,payload_json FROM mes_outbox
                   WHERE sent_at IS NULL AND delivery_status='PENDING'
                   ORDER BY id LIMIT ?""", (limit,)
            ).fetchall()
        for row in rows:
            try:
                request = urllib.request.Request(
                    self.events_url,
                    row["payload_json"].encode("utf-8"),
                    {"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=4) as response:
                    if not 200 <= response.status < 300:
                        raise RuntimeError(f"HTTP {response.status}")
                with self.connect() as db:
                    db.execute(
                        """UPDATE mes_outbox SET sent_at=?,attempts=attempts+1,
                           last_error=NULL,delivery_status='SENT' WHERE id=?""",
                        (now_ms(), row["id"]),
                    )
                self.online = True
                sent += 1
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
                if 400 <= exc.code < 500:
                    with self.connect() as db:
                        db.execute(
                            """UPDATE mes_outbox SET attempts=attempts+1,last_error=?,
                               delivery_status='REJECTED' WHERE id=?""",
                            (f"HTTP {exc.code}: {detail}", row["id"]),
                        )
                    self.online = True
                    continue
                self.online = False
                with self.connect() as db:
                    db.execute(
                        "UPDATE mes_outbox SET attempts=attempts+1,last_error=? WHERE id=?",
                        (f"HTTP {exc.code}: {detail}", row["id"]),
                    )
                break
            except Exception as exc:
                self.online = False
                with self.connect() as db:
                    db.execute(
                        "UPDATE mes_outbox SET attempts=attempts+1,last_error=? WHERE id=?",
                        (str(exc)[:500], row["id"]),
                    )
                break
        return sent

    def mes_json(self, method, path, payload=None, timeout=8):
        """Call a station-safe MES endpoint. No production decision is made locally."""
        url = self.mes_url + path
        body = None if payload is None else json.dumps(
            {"payload": payload}, ensure_ascii=False
        ).encode("utf-8")
        request = urllib.request.Request(
            url, body, {"Content-Type": "application/json"}, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            self.online = True
            return result
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                message = json.loads(detail).get("message") or json.loads(detail).get("error", {}).get("message")
            except Exception:
                message = detail
            raise RuntimeError(message or f"MES HTTP {exc.code}") from exc
        except Exception:
            self.online = False
            raise

    def _save_loading_state(self, value):
        with self.connect() as db:
            db.execute(
                """INSERT INTO pda_loading_state(key,value_json,updated_at)
                   VALUES('current',?,?)
                   ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,
                   updated_at=excluded.updated_at""",
                (json.dumps(value or {}, ensure_ascii=False), now_ms()),
            )

    def loading_state(self):
        with self.connect() as db:
            row = db.execute(
                "SELECT value_json FROM pda_loading_state WHERE key='current'"
            ).fetchone()
        return json.loads(row["value_json"]) if row else {}

    def start_loading(self, work_order_code, operator_badge, pcb_sn="",
                      bypass_pcb_sn_binding=False, bypass_reason="",
                      bypass_authorized_by=""):
        if self.code != "smt_pda_loading":
            raise ValueError("Material loading is only available at the PDA loading station.")
        draft = {
            "workOrderCode": str(work_order_code).strip().upper(),
            "operatorBadge": str(operator_badge).strip().upper(),
            "pcbSn": str(pcb_sn).strip().upper(),
            "bypassPcbSnBinding": bool(bypass_pcb_sn_binding),
            "bypassReason": str(bypass_reason).strip(),
            "bypassAuthorizedBy": str(bypass_authorized_by).strip().upper(),
        }
        if not all((draft["workOrderCode"], draft["operatorBadge"])):
            raise ValueError("Work order and operator badge are required.")
        if not draft["pcbSn"] and not draft["bypassPcbSnBinding"]:
            raise ValueError("Scan PCB SN from SPI or use authorized bypass.")
        if draft["bypassPcbSnBinding"] and not all(
            (draft["bypassReason"], draft["bypassAuthorizedBy"])
        ):
            raise ValueError("Bypass reason and line-leader badge are required.")
        # The machine position is deliberately not selectable or defaulted.
        # Both physical positions must be identified by the first scanner read.
        state = {"session": {}, "step": "MACHINE", "draft": draft, "bindings": []}
        self._save_loading_state(state)
        return state

    def loading_scan(self, value):
        """Consume one scanner value in the fixed slot->feeder->reel->operator sequence."""
        state = self.loading_state()
        session = state.get("session") or {}
        if not session and state.get("step") != "MACHINE":
            raise ValueError("Press Start Loading first.")
        value = str(value or "").strip().upper()
        if not value:
            raise ValueError("Scan value is empty.")
        step = state.get("step", "SLOT")
        draft = state.setdefault("draft", {})
        if step == "MACHINE":
            result = self.mes_json("POST", "/smt/loading/start", {
                "workOrderCode": draft["workOrderCode"],
                "lineCode": LINE_CODE,
                "machineCode": value,
                "operatorBadge": draft["operatorBadge"],
                "deviceId": socket.gethostname(),
                "pcbSn": draft.get("pcbSn") or None,
                "bypassPcbSnBinding": bool(draft.get("bypassPcbSnBinding")),
                "bypassReason": draft.get("bypassReason") or None,
                "bypassAuthorizedBy": draft.get("bypassAuthorizedBy") or None,
            })
            state["session"] = result["data"]
            state["machineCode"] = value
            state["draft"] = {}
            state["step"] = "SLOT"
        elif step == "SLOT":
            draft["slotNo"] = value
            state["step"] = "FEEDER"
        elif step == "FEEDER":
            draft["feederCode"] = value
            state["step"] = "REEL"
        elif step == "REEL":
            parts = [part.strip().upper() for part in value.replace("|", ",").split(",")]
            if len(parts) < 2:
                raise ValueError("Reel scan must contain MATERIAL_CODE,LOT_NO[,DATE_CODE].")
            draft["materialCode"], draft["lotNo"] = parts[0], parts[1]
            draft["dateCode"] = parts[2] if len(parts) > 2 else ""
            state["step"] = "OPERATOR"
        elif step == "OPERATOR":
            draft["operatorBadge"] = value
            state["step"] = "CONFIRM"
        else:
            raise ValueError("Confirm or cancel the current binding before scanning again.")
        self._save_loading_state(state)
        return state

    def confirm_loading_binding(self, qty=0):
        state = self.loading_state()
        session, draft = state.get("session") or {}, state.get("draft") or {}
        required = ("slotNo", "feederCode", "materialCode", "lotNo", "operatorBadge")
        if not session or any(not draft.get(key) for key in required):
            raise ValueError("The five-step scan is incomplete.")
        payload = {
            "sessionId": session["id"],
            "machineCode": session["machine_code"],
            "channelCode": draft.get("channelCode"),
            "slotNo": draft["slotNo"],
            "feederCode": draft["feederCode"],
            "lotNo": draft["lotNo"],
            "materialCode": draft["materialCode"],
            "dateCode": draft.get("dateCode"),
            "operatorBadge": draft["operatorBadge"],
            "qty": float(qty or 0),
        }
        result = self.mes_json("POST", "/smt/loading/bind", payload)
        state["draft"] = {}
        state["step"] = "SLOT"
        state.setdefault("bindings", []).append(result["data"])
        self._save_loading_state(state)
        return state

    def release_loading(self, line_leader_badge):
        state = self.loading_state()
        session = state.get("session") or {}
        badge = str(line_leader_badge or "").strip().upper()
        if not session or not badge:
            raise ValueError("Active session and line-leader badge are required.")
        result = self.mes_json("POST", "/smt/loading/release", {
            "sessionId": session["id"], "lineLeaderBadge": badge,
        })
        state["session"] = result["data"]
        state["step"] = "RELEASED"
        self._save_loading_state(state)
        return state

    def change_loading_roll(self, slot_no, new_reel_scan, operator_badge, old_remaining_qty=0):
        state = self.loading_state()
        session = state.get("session") or {}
        parts = [part.strip().upper() for part in str(new_reel_scan).replace("|", ",").split(",")]
        if not session or len(parts) < 2:
            raise ValueError("Active session and MATERIAL_CODE,LOT_NO reel scan are required.")
        result = self.mes_json("POST", "/smt/loading/roll-change", {
            "sessionId": session["id"],
            "slotNo": str(slot_no).strip().upper(),
            "newMaterialCode": parts[0],
            "newLotNo": parts[1],
            "operatorBadge": str(operator_badge).strip().upper(),
            "oldRemainingQty": float(old_remaining_qty or 0),
        })
        old_id = result["data"]["oldBinding"]["id"]
        state["bindings"] = [
            item for item in state.get("bindings", []) if item.get("id") != old_id
        ]
        state["bindings"].append(result["data"]["newBinding"])
        self._save_loading_state(state)
        return state

    def heartbeat(self):
        return self.queue("AGENT_HEARTBEAT", {
            "agent": "smt_station_agent",
            "agentVersion": "2.0.0",
            "status": "running",
            "stationName": self.cfg["nameZh"],
            "nameEn": self.cfg["nameEn"],
            "nameVi": self.cfg["nameVi"],
            "sourceType": self.cfg["sourceType"],
            "sourceStatus": self.cfg.get("source", {}).get("status", "pending"),
            "configuredIp": self.station_ip or None,
            "responsibilities": self.responsibilities(),
            "standardsProfile": ["IPC-2591-CFX", "IPC-HERMES-9852-COMPATIBLE"],
        })

    def responsibilities(self):
        return COMMON_RESPONSIBILITIES + STATION_RESPONSIBILITIES.get(self.code, [])

    def activity(self, activity_type, sn="", detail=None):
        """Record and publish WIP lifecycle without inventing production facts."""
        allowed = {
            "UNIT_ARRIVED", "WORK_STARTED", "WORK_STAGE_STARTED", "WORK_STAGE_COMPLETED",
            "WORK_PAUSED", "WORK_RESUMED", "WORK_COMPLETED", "UNIT_DEPARTED",
            "RECIPE_ACTIVATED", "RECIPE_MODIFIED", "MATERIAL_LOADED", "MATERIAL_UNLOADED",
            "TOOL_USED", "READING_RECORDED", "MAINTENANCE_PERFORMED",
            "HERMES_BOARD_AVAILABLE", "HERMES_TRANSPORT_STARTED", "HERMES_TRANSPORT_FINISHED",
            "HERMES_CONNECTION_LOST",
        }
        activity_type = str(activity_type or "").strip().upper()
        if activity_type not in allowed:
            raise ValueError(f"Unsupported station activity: {activity_type}")
        sn = str(sn or "").strip().upper()
        detail = detail or {}
        event_id = self.queue("SMT_STATION_ACTIVITY", {
            "activityType": activity_type, "sn": sn or None, "detail": detail,
            "formalProductionFact": False,
        })
        with self.connect() as db:
            db.execute(
                """INSERT OR IGNORE INTO station_activity
                   (event_id,activity_type,sn,detail_json,occurred_at) VALUES(?,?,?,?,?)""",
                (event_id, activity_type, sn or None, json.dumps(detail, ensure_ascii=False), now_ms()),
            )
        return event_id

    def recipe_event(self, recipe_id, revision="", modified=False, operator=""):
        if not str(recipe_id or "").strip():
            raise ValueError("recipe_id is required.")
        return self.activity(
            "RECIPE_MODIFIED" if modified else "RECIPE_ACTIVATED",
            detail={"recipeId": str(recipe_id), "revision": str(revision), "operator": str(operator)},
        )

    def material_event(self, material_id, carrier_id="", location="", loaded=True, quantity=None):
        if not str(material_id or "").strip():
            raise ValueError("material_id is required.")
        return self.activity(
            "MATERIAL_LOADED" if loaded else "MATERIAL_UNLOADED",
            detail={"materialId": str(material_id), "carrierId": str(carrier_id),
                    "location": str(location), "quantity": quantity},
        )

    def tool_event(self, tool_id, sn="", detail=None):
        if not str(tool_id or "").strip():
            raise ValueError("tool_id is required.")
        return self.activity("TOOL_USED", sn, {"toolId": str(tool_id), **(detail or {})})

    def measurement_event(self, sn, measurements, inspection_kind=""):
        if not isinstance(measurements, dict) or not measurements:
            raise ValueError("measurements must be a non-empty object.")
        return self.activity("READING_RECORDED", sn, {
            "inspectionKind": inspection_kind or (
                "SPI" if self.code == "smt_spi" else "AOI" if self.code == "smt_aoi" else "PROCESS"
            ),
            "measurements": measurements,
        })

    def fault(self, fault_code, message, severity="ERROR"):
        fault_code = str(fault_code or "").strip().upper()
        severity = str(severity or "ERROR").strip().upper()
        if not fault_code or severity not in {"INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("Valid fault_code and severity are required.")
        with self.connect() as db:
            db.execute(
                """INSERT INTO active_faults(fault_code,severity,message,occurred_at,acknowledged_at,cleared_at)
                   VALUES(?,?,?,?,NULL,NULL)
                   ON CONFLICT(fault_code) DO UPDATE SET severity=excluded.severity,
                   message=excluded.message,occurred_at=excluded.occurred_at,
                   acknowledged_at=NULL,cleared_at=NULL""",
                (fault_code, severity, str(message), now_ms()),
            )
        return self.queue("STATION_FAULT_OCCURRED", {
            "faultCode": fault_code, "message": str(message), "severity": severity,
        })

    def acknowledge_fault(self, fault_code, operator):
        with self.connect() as db:
            changed = db.execute(
                "UPDATE active_faults SET acknowledged_at=? WHERE fault_code=? AND cleared_at IS NULL",
                (now_ms(), str(fault_code).strip().upper()),
            ).rowcount
        if not changed:
            raise ValueError("Active fault not found.")
        return self.queue("STATION_FAULT_ACKNOWLEDGED", {
            "faultCode": str(fault_code).strip().upper(), "operator": str(operator),
        })

    def clear_fault(self, fault_code, operator, resolution):
        with self.connect() as db:
            changed = db.execute(
                "UPDATE active_faults SET cleared_at=? WHERE fault_code=? AND cleared_at IS NULL",
                (now_ms(), str(fault_code).strip().upper()),
            ).rowcount
        if not changed:
            raise ValueError("Active fault not found.")
        return self.queue("STATION_FAULT_CLEARED", {
            "faultCode": str(fault_code).strip().upper(),
            "operator": str(operator), "resolution": str(resolution),
        })

    def scan(self, sn):
        sn = str(sn or "").strip().upper()
        if len(sn) < 3:
            decision, detail = "REJECT", "INVALID_SN"
        else:
            decision, detail = "PENDING_MES_GUARD", "CHECK_ONLY"
            self.queue("SCAN_GUARD_CHECK", {
                "sn": sn,
                "mode": "CHECK_ONLY",
                "registerSn": False,
                "checks": ["CONFIRMED_NG", "DUPLICATE_SN", "ROUTE_SEQUENCE"],
            })
        with self.connect() as db:
            db.execute(
                "INSERT INTO scan_audit(sn,decision,detail,scanned_at) VALUES(?,?,?,?)",
                (sn, decision, detail, now_ms()),
            )
        return {"allowed": decision != "REJECT", "decision": decision, "reason": detail, "sn": sn}

    def production_result(self, sn, result, source_ref="", raw=None, source_key=None):
        sn = str(sn or "").strip().upper()
        normalized = RESULT_ALIASES.get(str(result or "").strip().upper())
        if not sn or not normalized:
            raise ValueError("Trusted result requires a valid SN and PASS/NG result.")
        raw = raw or {"sn": sn, "result": result}
        source_key = source_key or hashlib.sha256(
            (str(source_ref) + "\0" + json.dumps(raw, sort_keys=True, ensure_ascii=False)).encode("utf-8")
        ).hexdigest()
        with self.connect() as db:
            cursor = db.execute(
                """INSERT OR IGNORE INTO raw_records
                   (source_key,source_ref,sn,result,raw_json,captured_at)
                   VALUES(?,?,?,?,?,?)""",
                (source_key, str(source_ref), sn, normalized,
                 json.dumps(raw, ensure_ascii=False), now_ms()),
            )
            inserted = cursor.rowcount > 0
        if not inserted:
            return {"duplicateEvidence": True, "sourceKey": source_key}
        captured_at = now_ms()
        event_type = "STATION_TEST_RESULT" if normalized == "PASS" else "NG_DEFECT"
        event_id = self.queue(event_type, {
            "sn": sn,
            "result": "PASS" if normalized == "PASS" else "FAIL",
            "sourceRef": str(source_ref),
            "sourceKey": source_key,
            "trustedSource": True,
            "registerSn": True,
            "eventType": "SMT_TRUSTED_SOURCE_RESULT",
            "sourceType": self.cfg["sourceType"],
            "sourceTestTime": captured_at,
            "sourceTestTimeIso": time.strftime(
                "%Y-%m-%dT%H:%M:%S%z", time.localtime(captured_at / 1000)
            ),
            "productionDate": time.strftime("%Y-%m-%d", time.localtime(captured_at / 1000)),
            "batchId": str(raw.get("batchId") or raw.get("batch_id") or sn),
            "lineName": LINE_CODE,
            "isConfirmed": normalized == "NG",
            "firstDetectedAt": captured_at if normalized == "NG" else None,
            "dispatchDeadlineAt": captured_at + 20 * 60 * 1000 if normalized == "NG" else None,
            "repairDeadlineAt": captured_at + 120 * 60 * 1000 if normalized == "NG" else None,
            "oneTimeNgConfirmation": True,
            "cfxSemantic": (
                "UNITS_INSPECTED" if self.code in {"smt_spi", "smt_aoi"}
                else "UNITS_PROCESSED"
            ),
            "responsibility": (
                "SOLDER_PASTE_INSPECTION" if self.code == "smt_spi"
                else "AUTOMATED_OPTICAL_INSPECTION" if self.code == "smt_aoi"
                else "PRODUCTION_PROCESS"
            ),
        })
        return {"eventId": event_id, "result": normalized, "sourceKey": source_key}

    def complete_process(self, sn, detail=None):
        """Create a route stamp without registering scanner input as a new SN."""
        sn = str(sn or "").strip().upper()
        if len(sn) < 3:
            raise ValueError("A valid SN is required.")
        return self.queue("STATION_PROCESS_COMPLETED", {
            "sn": sn,
            "result": "PASS",
            "registerSn": False,
            "scannerObservationOnly": self.cfg["sourceType"] == "scanner",
            "formalProductionFact": False,
            "detail": detail or {},
        })

    def send_ng_to_repair(self, sn, operator, defect_code="", defect_description=""):
        """Request the physical NG handover. MES creates and supervises the repair WO."""
        sn = str(sn or "").strip().upper()
        operator = str(operator or "").strip()
        if len(sn) < 3 or not operator:
            raise ValueError("A valid SN and operator are required.")
        with self.connect() as db:
            ng = db.execute(
                """SELECT result,captured_at,raw_json FROM raw_records
                   WHERE UPPER(sn)=UPPER(?) AND result='NG'
                   ORDER BY captured_at DESC LIMIT 1""", (sn,)
            ).fetchone()
        if not ng:
            raise ValueError("No trusted NG record exists for this SN.")
        return self.queue("STATION_ROUTE_SELECTED", {
            "sn": sn,
            "batchId": sn,
            "destination": "MAINTENANCE",
            "destinationStationCode": "manu_rework",
            "destinationLabel": "维修站 / Maintenance",
            "workflowCode": "MES_REPAIR_HANDOVER",
            "operator": operator,
            "defectCode": str(defect_code or f"{self.code.upper()}_FAIL"),
            "defectDescription": str(defect_description or "SMT confirmed NG"),
            "firstDetectedAt": int(ng["captured_at"]),
            "dispatchDeadlineAt": int(ng["captured_at"]) + 20 * 60 * 1000,
            "repairDeadlineAt": int(ng["captured_at"]) + 120 * 60 * 1000,
            "mesSupervised": True,
            "operatorConfirmationRequired": True,
        })

    def _parse_csv(self, path):
        aliases = self.cfg.get("source", {}).get("columns", {})
        sn_names = [x.lower() for x in aliases.get("sn", ["sn", "serial", "serialnumber", "barcode"])]
        result_names = [x.lower() for x in aliases.get("result", ["result", "status", "testresult", "judge"])]
        records = []
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                lowered = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
                sn = next((lowered[k] for k in sn_names if lowered.get(k)), "")
                result = next((lowered[k] for k in result_names if lowered.get(k)), "")
                if sn and RESULT_ALIASES.get(str(result).strip().upper()):
                    records.append((sn, result, row))
        return records

    def ingest_file(self, path):
        path = Path(path)
        if not path.is_file():
            return 0
        suffix = path.suffix.lower()
        if suffix == ".csv":
            records = self._parse_csv(path)
        elif suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            data = data if isinstance(data, list) else [data]
            records = [(x.get("sn"), x.get("result"), x) for x in data]
        else:
            return 0
        count = 0
        for index, (sn, result, raw) in enumerate(records):
            source_key = hashlib.sha256(
                (str(path.resolve()) + f":{index}:" + json.dumps(raw, sort_keys=True, ensure_ascii=False)).encode("utf-8")
            ).hexdigest()
            outcome = self.production_result(sn, result, str(path), raw, source_key)
            count += 0 if outcome.get("duplicateEvidence") else 1
        return count

    def watch_once(self):
        source = self.cfg.get("source", {})
        directory = str(source.get("path") or "").strip()
        if not directory or source.get("status") == "pending":
            return 0
        root = Path(directory)
        if not root.exists():
            self.last_message = f"Source unavailable: {root}"
            return 0
        total = 0
        for pattern in source.get("patterns", ["*.csv", "*.json"]):
            for path in sorted(root.glob(pattern), key=lambda item: item.stat().st_mtime):
                if time.time() - path.stat().st_mtime >= 2:
                    total += self.ingest_file(path)
        return total

    def counts(self):
        with self.connect() as db:
            raw = db.execute("SELECT COUNT(*) n FROM raw_records").fetchone()["n"]
            scans = db.execute("SELECT COUNT(*) n FROM scan_audit").fetchone()["n"]
            pending = db.execute(
                "SELECT COUNT(*) n FROM mes_outbox WHERE sent_at IS NULL AND delivery_status='PENDING'"
            ).fetchone()["n"]
            faults = db.execute("SELECT COUNT(*) n FROM active_faults WHERE cleared_at IS NULL").fetchone()["n"]
        return {"rawRecords": raw, "scanChecks": scans, "pendingSync": pending, "activeFaults": faults}

    def recent_resources(self, limit=100):
        limit = max(1, min(int(limit), 500))
        with self.connect() as db:
            raw = [dict(row) for row in db.execute(
                """SELECT source_ref,sn,result,raw_json,captured_at
                   FROM raw_records ORDER BY id DESC LIMIT ?""", (limit,)
            ).fetchall()]
            activities = [dict(row) for row in db.execute(
                """SELECT activity_type,sn,detail_json,occurred_at
                   FROM station_activity ORDER BY id DESC LIMIT ?""", (limit,)
            ).fetchall()]
            faults = [dict(row) for row in db.execute(
                """SELECT fault_code,severity,message,occurred_at,acknowledged_at,cleared_at
                   FROM active_faults ORDER BY occurred_at DESC LIMIT ?""", (limit,)
            ).fetchall()]
            outbox = [dict(row) for row in db.execute(
                """SELECT event_id,event_type,created_at,sent_at,attempts,last_error,delivery_status
                   FROM mes_outbox ORDER BY id DESC LIMIT ?""", (limit,)
            ).fetchall()]
        return {"raw": raw, "activities": activities, "faults": faults, "outbox": outbox}

    def self_test(self):
        assert 0 <= int(self.cfg["sequence"]) <= 6
        assert self.cfg["sourceType"] in {"scanner", "machine", "database", "file"}
        assert not self.station_ip or self.station_ip.count(".") == 3
        return {
            "ok": True, "stationCode": self.code, "domain": DOMAIN,
            "lineCode": LINE_CODE, "stationIp": self.station_ip or "PENDING",
            "counts": self.counts(), "responsibilities": self.responsibilities(),
        }

    def run(self):
        lock = SingleInstance(self.code, self.station_dir).acquire()
        try:
            next_heartbeat = 0
            while not self.stop_event.wait(1):
                stamp = time.monotonic()
                if stamp >= next_heartbeat:
                    self.heartbeat()
                    next_heartbeat = stamp + int(self.cfg.get("heartbeatSeconds", 10))
                self.watch_once()
                self.flush()
        finally:
            lock.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--heartbeat-once", action="store_true")
    parser.add_argument("--scan")
    parser.add_argument("--result", choices=("PASS", "NG"))
    parser.add_argument("--ingest-file")
    args = parser.parse_args()
    agent = SmtStationAgent(args.config)
    if args.self_test:
        print(json.dumps(agent.self_test(), ensure_ascii=False))
    elif args.heartbeat_once:
        agent.heartbeat()
        print(json.dumps({"ok": True, "heartbeat": agent.code}, ensure_ascii=False))
    elif args.ingest_file:
        print(json.dumps({"ingested": agent.ingest_file(args.ingest_file)}, ensure_ascii=False))
    elif args.result:
        print(json.dumps(agent.production_result(args.scan or "TEST-SN", args.result, "command-line"), ensure_ascii=False))
    elif args.scan:
        print(json.dumps(agent.scan(args.scan), ensure_ascii=False))
    else:
        agent.run()


if __name__ == "__main__":
    main()
