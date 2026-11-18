# -*- coding: utf-8 -*-
"""Shared MES repair handover and repair-return receipt UI for Tk stations."""
from __future__ import annotations

import datetime
import json
import logging
import os
from pathlib import Path
from station_common_agent import build_common_agent
from station_i18n import TrilingualController
import socket
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import urllib.error
import urllib.parse
import urllib.request

RESERVOIR_PY = Path(__file__).resolve().parents[1] / "station-component-reservoir" / "python"
if str(RESERVOIR_PY) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(RESERVOIR_PY))
from station_components.ng_closed_loop import append_history
from station_components.repair_cycle_graph import cycle_projection
from repair_work_order_store import init_store, latest_work_orders, upsert_work_order
from station_resource_viewer import build_resource_view, render_resource_view

COMPONENT_VERSION = "4.1-shared-ng-history"
SHARED_REPAIR_COMPONENT = "quality.repair.shared-ng-history"
PROCESS_DOMAINS = {"AUTO_LINE", "MANUAL_LINE"}
DEFAULT_LINE_CODES = {"AUTO_LINE": "L002", "MANUAL_LINE": "L004"}

_repair_logger = logging.getLogger("station_repair_workflow")


def log(message):
    """Keep repair-cache diagnostics from crashing station startup."""
    _repair_logger.warning(str(message))


def _process_context(station_code):
    """Resolve MES process domain and line from station identity/configuration."""
    code = str(station_code or "").strip().lower()
    configured_domain = os.getenv("STATION_PROCESS_DOMAIN", "").strip().upper()
    domain = configured_domain if configured_domain in PROCESS_DOMAINS else (
        "AUTO_LINE" if code.startswith("auto_") else "MANUAL_LINE"
    )
    line_code = os.getenv("STATION_LINE_CODE", "").strip() or DEFAULT_LINE_CODES[domain]
    return domain, line_code
NG_LOOP_FLOW_NAME = "MES Agent Closed-Loop Delivery Flow"
NG_LOOP_STAGES = (
    "ALIGNMENT", "ROUTE_PLAN", "SPECIFICATION", "TASK_BREAKDOWN",
    "IMPLEMENTATION", "TEST", "CODE_REVIEW", "DEPLOYMENT",
    "FIELD_VERIFICATION", "HANDOFF",
)
_LAST_HEARTBEAT = {}
ROUTING_GRAPH_PATH = Path(__file__).with_name("ng-routing.graph.json")


def _load_ng_routing_graph():
    """Load the MES-published NG graph; fail closed if it is absent/invalid."""
    try:
        graph = json.loads(ROUTING_GRAPH_PATH.read_text(encoding="utf-8"))
        if graph.get("authority") != "MES" or not graph.get("graphId"):
            raise ValueError("NG routing graph must be MES-authorized")
        node_ids = {str(node.get("id")) for node in graph.get("nodes", [])}
        if not node_ids or any(edge.get("from") not in node_ids or edge.get("to") not in node_ids
                               for edge in graph.get("edges", [])):
            raise ValueError("NG routing graph contains an invalid edge")
        normal_route = graph.get("configuration", {}).get("normalRoute", [])
        if not normal_route or any(node not in node_ids for node in normal_route):
            raise ValueError("NG routing graph contains an invalid normal route")
        return graph
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"graphId": "UNAVAILABLE", "schemaVersion": "", "authority": "MES",
                "nodes": [], "edges": []}


def _routing_metadata(graph):
    return {"routeGraphId": graph.get("graphId", "UNAVAILABLE"),
            "routeGraphVersion": graph.get("schemaVersion", ""),
            "routeAuthority": graph.get("authority", "MES")}


def _routing_available(graph):
    return bool(graph.get("graphId") and graph.get("graphId") != "UNAVAILABLE"
                and graph.get("authority") == "MES")


def _ng_loop_metadata(policy, actor, stage="IMPLEMENTATION"):
    """Return auditable metadata shared by manual-line NG handovers."""
    stage = str(stage or "IMPLEMENTATION").upper()
    if stage not in NG_LOOP_STAGES:
        raise ValueError(f"unsupported NG loop stage: {stage}")
    return {
        "deliveryFlow": NG_LOOP_FLOW_NAME,
        "deliveryFlowStage": stage,
        "policyVersion": policy.get("version") or policy.get("policyVersion") or "",
        "policyReason": policy.get("configReason") or "",
        "actor": str(actor or ""),
        "recordingRule": "append-only; MES owns route, repair authority, and closure",
        "sharedRepairComponent": SHARED_REPAIR_COMPONENT,
        "sharedRepairComponentVersion": COMPONENT_VERSION,
    }


def _host_identity():
    hostname = socket.gethostname()
    addresses = []
    try:
        addresses = socket.gethostbyname_ex(hostname)[2]
    except OSError:
        pass
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("192.168.6.155", 8080))
        addresses.insert(0, probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    host_ip = next((ip for ip in addresses if ip and not ip.startswith("127.")), "127.0.0.1")
    return hostname, host_ip


def _component_heartbeat(station_code, mes_base_url, policy=None):
    base = str(mes_base_url).replace("/api/pda/events", "").rstrip("/")
    hostname, host_ip = _host_identity()
    process_domain, line_code = _process_context(station_code)
    payload = {
        "type": "AGENT_HEARTBEAT", "stationCode": station_code,
        "from": "repair_workflow_component", "to": "mes_server",
        "payload": {"agent": "station_repair_workflow", "agentVersion": COMPONENT_VERSION,
                    "component": "repair_workflow", "status": "running",
                    "processDomain": process_domain, "lineCode": line_code,
                    "hostname": hostname, "hostIp": host_ip,
                    "policyMode": (policy or {}).get("actionMode"),
                    "policyVersion": (policy or {}).get("version"),
                    "timestamp": int(time.time() * 1000)},
    }
    return _json_request(base + "/api/pda/events", "POST", payload)


DEFAULT_REPAIR_POLICY = {
    "enabled": True,
    "actionMode": "SEND_REPAIR",
    "slaMinutes": 30,
    "repairDestination": "manu_rework",
    "maxRetestCount": 2,
    "allowedRoles": ["OPERATOR", "QC", "LINE_LEADER"],
    "requireOperator": True,
    "allowRepairReturn": True,
    "allowRepairDispatch": True,
    "dispatchMode": "AUTOMATIC",
    "automaticActor": "MES_POLICY_ENGINE",
    # PMC owns the production-plan quantity/window; MES owns the NG route.
    "pmcRequired": True,
    "pmcScheduleSource": "PMC",
    "pmcApprovalRequired": True,
    "instruction": "确认NG后送往回修站",
    "timeThresholdMinutes": 30,
    "quantityThreshold": 10,
    "triggerMode": "ANY",
    "humanButtonEnabled": True,
    "dispatchTiming": "ANY_TIME",
    "designatedTime": "15:00",
    "shiftEndTime": "17:00",
    "escalationMinutes": 30,
    "repeatNgWindowHours": 24,
    "repeatNgThreshold": 2,
    "priority": "NORMAL",
    "qcApprovalRequired": False,
    "lineLeaderApprovalRequired": False,
    "returnStationMode": "ORIGIN",
    "designatedReturnStation": "",
    "offlinePolicy": "BLOCK",
    "evidenceRequired": False,
    "configReason": "MES default repair policy",
    "effectiveFrom": "",
}

STATION_REPAIR_POLICY_DEFAULTS = {
    "manu_ict": {
        "actionMode": "MARK_ONLY",
        "allowRepairDispatch": False,
        "repairDestination": "manu_depanel",
        "instruction": "记录ICT NG并随母板流转到分板机；禁止本站直接创建维修工单",
        "configReason": "ICT NG must be physically separated at depanel before repair dispatch",
    },
    "manu_fct": {
        "actionMode": "MARK_ONLY",
        "allowRepairDispatch": False,
        "repairDestination": "manu_depanel",
        "instruction": "记录FCT NG并随母板流转到分板机；禁止本站直接创建维修工单",
        "configReason": "FCT NG must be physically separated at depanel before repair dispatch",
    },
    "manu_depanel": {
        "actionMode": "SEND_REPAIR",
        "allowRepairDispatch": False,
        "repairDestination": "manu_rework",
        "instruction": "物理挑出NG子板后，由分板专用流程创建唯一维修工单",
        "configReason": "Depanel is the single physical repair-dispatch point",
    },
}


def _repair_policy(items, station_code):
    """Resolve the station policy from the MES repair_policy projection."""
    policy = dict(DEFAULT_REPAIR_POLICY)
    policy.update(STATION_REPAIR_POLICY_DEFAULTS.get(station_code, {}))
    for bucket in items:
        if (str(bucket.get("stationCode", "")).lower() == station_code
                and bucket.get("bucketName") == "repair_policy"):
            payload = bucket.get("payload") or {}
            if isinstance(payload, list):
                payload = payload[0] if payload else {}
            if isinstance(payload, dict):
                policy.update({key: value for key, value in payload.items() if value is not None})
            break
    mode = str(policy.get("actionMode") or "SEND_REPAIR").upper()
    if mode not in {"SEND_REPAIR", "MARK_ONLY", "REMOVE_IMMEDIATELY"}:
        mode = "SEND_REPAIR"
    policy["actionMode"] = mode
    policy["slaMinutes"] = max(1, int(policy.get("slaMinutes") or 30))
    policy["timeThresholdMinutes"] = max(1, int(policy.get("timeThresholdMinutes") or 30))
    policy["quantityThreshold"] = max(1, int(policy.get("quantityThreshold") or 10))
    policy["maxRetestCount"] = max(0, int(policy.get("maxRetestCount") if policy.get("maxRetestCount") is not None else 2))
    for key, default in (("escalationMinutes", 30), ("repeatNgWindowHours", 24), ("repeatNgThreshold", 2)):
        policy[key] = max(1, int(policy.get(key) or default))
    timing = str(policy.get("dispatchTiming") or "ANY_TIME").upper()
    policy["dispatchTiming"] = timing if timing in {"ANY_TIME", "DESIGNATED_TIME", "END_OF_SHIFT"} else "ANY_TIME"
    return policy


def _dispatch_readiness(policy, rows, now_ms=None):
    now_ms = int(now_ms or time.time() * 1000)
    count = len(rows)
    oldest = now_ms
    for row in rows:
        detected = RepairWorkflowPanel._millis(row.get("firstDetectedAt") or row.get("ngDetectedAt") or row.get("testTime") or row.get("time"))
        oldest = min(oldest, detected)
    age_minutes = max(0, (now_ms - oldest) // 60000) if rows else 0
    threshold_ready = count >= policy["quantityThreshold"] or age_minutes >= policy["timeThresholdMinutes"]
    timing = policy["dispatchTiming"]
    clock = datetime.datetime.fromtimestamp(now_ms / 1000).strftime("%H:%M")
    window_ready = (timing == "ANY_TIME" or
                    timing == "DESIGNATED_TIME" and clock >= str(policy.get("designatedTime") or "00:00") or
                    timing == "END_OF_SHIFT" and clock >= str(policy.get("shiftEndTime") or "00:00"))
    ready = bool(rows) and threshold_ready and window_ready
    reason = f"NG {count}/{policy['quantityThreshold']} · 最老 {age_minutes}/{policy['timeThresholdMinutes']}分钟 · {timing}"
    return ready, reason


def _json_request(url, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8") or "{}")
            message = detail.get("message") or detail.get("error", {}).get("message")
        except Exception:
            message = ""
        raise RuntimeError(message or f"MES HTTP {exc.code}") from exc


class RepairWorkflowPanel:
    def __init__(self, root, station_code, mes_base_url, station_name="", preview=False):
        self.root = root
        self.station_code = str(station_code).strip().lower()
        self.station_name = station_name or self.station_code
        self.process_domain, self.line_code = _process_context(self.station_code)
        self.base = str(mes_base_url).replace("/api/pda/events", "").rstrip("/")
        self.preview = bool(preview)
        self.ng_rows = {}
        self.return_rows = {}
        self._automatic_inflight = set()
        self.policy = dict(DEFAULT_REPAIR_POLICY)
        self.route_graph = _load_ng_routing_graph()
        try:
            init_store(self.station_code)
        except Exception as exc:
            # A station must still start if its local cache is temporarily
            # unavailable; MES connectivity and the alarm surface remain live.
            log(f"[REPAIR][LOCAL_DB] deferred for {self.station_code}: {exc}")
        # All stations use the same top-right launcher. ICT explicitly
        # reserves its top toolbar for shared controls; other stations get a
        # compact top strip before their main header.
        # Reuse the existing retest/action host so repair sits beside the
        # retest button without adding a separate header line.
        host = getattr(root, "_retest_host", None) or getattr(root, "_repair_host", None)
        if host is None:
            host = tk.Frame(root, bg="#101d27", padx=8, pady=4)
            host.pack(side="top", fill="x")
            host.pack_propagate(False)
            host.configure(height=54)
        self.frame = tk.Frame(host, bg="#101d27")
        self.frame.pack(side="right", padx=(6, 0), pady=6)
        repair_button = tk.Button(
            self.frame, text="维修闭环 / REPAIR", command=self.open,
            bg="#dc2626", activebackground="#b91c1c", fg="white",
            font=("Microsoft YaHei UI", 11, "bold"), width=24, padx=14, pady=9,
        )
        repair_button._preserve_bilingual = True
        repair_button.pack(side="left")
        resource_button = tk.Button(
            self.frame, text="资源查看 / RESOURCES", command=self.open_resources,
            bg="#2563eb", activebackground="#1d4ed8", fg="white",
            font=("Microsoft YaHei UI", 10, "bold"), width=24, padx=14, pady=7,
        )
        resource_button._preserve_bilingual = True
        resource_button.pack(side="left", padx=(6, 0))
        if not self.preview:
            self._heartbeat_tick()
            self._automation_tick()

    def _automation_tick(self):
        threading.Thread(target=self._automation_once, daemon=True,
                         name=f"repair-auto-{self.station_code}").start()
        self.root.after(2000, self._automation_tick)

    def open_resources(self):
        """Show human-readable SQLite/CSV/XLSX resources for this station."""
        view = build_resource_view(db_path=Path(__file__).with_name(f"repair_work_orders_{self.station_code}.db"))
        win = tk.Toplevel(self.root)
        win.title(f"{self.station_name} · LOCAL RESOURCES / 本地资源")
        win.geometry("980x700")
        text = tk.Text(win, wrap="none", font=("Consolas", 10), bg="#0f172a", fg="#e2e8f0")
        text.pack(fill="both", expand=True, padx=10, pady=10)
        text.insert("1.0", render_resource_view(view))
        text.configure(state="disabled")
        tk.Button(win, text="关闭 / CLOSE", command=win.destroy).pack(pady=(0, 10))

    def _automation_once(self):
        try:
            if not _routing_available(self.route_graph):
                return
            buckets = _json_request(self.base + "/api/station/bucket-snapshots").get("items", [])
            policy = _repair_policy(buckets, self.station_code)
            if (str(policy.get("dispatchMode") or "MANUAL").upper() != "AUTOMATIC"
                    or not policy.get("enabled", True)
                    or not policy.get("allowRepairDispatch", True)
                    or policy.get("actionMode") != "SEND_REPAIR"):
                return
            rows = []
            for bucket in buckets:
                if (str(bucket.get("stationCode", "")).lower() == self.station_code
                        and bucket.get("bucketName") == "confirmed_ng"):
                    rows.extend(bucket.get("payload") or [])
            ready, _reason = _dispatch_readiness(policy, rows)
            if not ready:
                return
            for row in rows:
                sn = str(row.get("sn") or row.get("ngSn") or "").strip().upper()
                if not sn:
                    continue
                batch_id = str(row.get("batchId") or sn)
                key = f"{self.station_code}:{batch_id}:{sn}"
                if key in self._automatic_inflight:
                    continue
                self._automatic_inflight.add(key)
                try:
                    detected = self._millis(row.get("firstDetectedAt") or row.get("ngDetectedAt") or row.get("testTime") or row.get("time"))
                    sla_minutes = int(policy.get("slaMinutes") or 30)
                    actor = str(policy.get("automaticActor") or "MES_POLICY_ENGINE")
                    payload = {
                        "processDomain": self.process_domain, "lineCode": self.line_code,
                        "eventId": f"{self.station_code}:REPAIR_DISPATCH:{batch_id}:{sn}",
                        "sourceStation": self.station_code, "sourceStationName": self.station_name,
                        "sourceProcessDomain": self.process_domain, "sourceLineCode": self.line_code,
                        "ngSn": sn, "batchId": batch_id, "members": [row],
                        "firstDetectedAt": detected,
                        "repairDeadlineAt": detected + sla_minutes * 60 * 1000,
                        "confirmedBy": actor, "confirmedRole": "SYSTEM",
                        "submittedBy": actor, "submittedRole": "SYSTEM",
                        "clickedAt": int(time.time() * 1000), "actionMode": "SEND_REPAIR",
                        "dispatchMode": "AUTOMATIC",
                        "sendSignalSource": "MES_RULE_ENGINE",
                        "pmcScheduleSource": policy.get("pmcScheduleSource") or "PMC",
                        "pmcRequired": bool(policy.get("pmcRequired", True)),
                        "pmcWorkOrderNo": row.get("pmcWorkOrderNo") or row.get("workOrderNo") or row.get("batchId") or "",
                        "pmcPlanVersion": row.get("pmcPlanVersion") or policy.get("pmcPlanVersion") or "",
                        "shipmentQuantity": row.get("shipmentQuantity") or row.get("quantity") or row.get("qty") or 0,
                        "quantitySource": "PMC" if (row.get("shipmentQuantity") or row.get("quantity") or row.get("qty")) else "MISSING",
                        "repairDestination": policy.get("repairDestination") or "manu_rework",
                        "maxRetestCount": int(policy.get("maxRetestCount") or 0),
                        "routePolicyVersion": policy.get("version") or policy.get("policyVersion") or "",
                        **_routing_metadata(self.route_graph),
                        "stationInstruction": policy.get("instruction") or "",
                        "policyReason": policy.get("configReason") or "",
                    }
                    payload.update(_ng_loop_metadata(policy, actor, "DEPLOYMENT"))
                    _json_request(self.base + "/api/station/maintenance-handovers", "POST", payload)
                except Exception:
                    self._automatic_inflight.discard(key)
        except Exception:
            return

    def _heartbeat_tick(self):
        threading.Thread(target=self._heartbeat_once, daemon=True,
                         name=f"repair-heartbeat-{self.station_code}").start()
        self.root.after(10000, self._heartbeat_tick)

    def _heartbeat_once(self):
        try:
            _component_heartbeat(self.station_code, self.base, self.policy)
        except Exception:
            pass

    def open(self):
        if getattr(self, "window", None) and self.window.winfo_exists():
            self.window.lift(); return
        self.window = tk.Toplevel(self.root)
        self.window.title("维修闭环 / REPAIR CLOSED LOOP")
        screen_w = max(760, self.window.winfo_screenwidth() - 40)
        screen_h = max(520, self.window.winfo_screenheight() - 80)
        self.window.geometry(f"{screen_w}x{screen_h}+20+20")
        self.window.minsize(760, 520)
        self.window.resizable(True, True)
        try:
            self.window.state("zoomed")
        except tk.TclError:
            pass
        self.window.configure(bg="#07111f")
        header = tk.Frame(self.window, bg="#10243b", padx=14, pady=10)
        header.pack(fill="x")
        tk.Label(header, text=f"{self.station_name} · 维修闭环", bg="#10243b", fg="white",
                 font=("Microsoft YaHei UI", 17, "bold")).pack(side="left")
        self.policy_summary = tk.StringVar(value="正在读取 MES 工站策略…")
        tk.Label(header, textvariable=self.policy_summary, bg="#10243b", fg="#fbbf24",
                 font=("Microsoft YaHei UI", 11, "bold")).pack(side="right")
        tk.Label(header, text=f"SHARED REPAIR {COMPONENT_VERSION}", bg="#10243b", fg="#86efac",
                 font=("Consolas", 10, "bold")).pack(side="right", padx=18)
        # The repair loop is a complete station surface, so it owns its own
        # language controls and translates every child widget (including
        # dialogs, tabs, headings, and live status variables).
        self.language_controller = TrilingualController(
            self.window, header, use_place=False, show_buttons=True
        )
        actions = tk.Frame(self.window, bg="#07111f", padx=12, pady=10); actions.pack(fill="x")
        tk.Button(actions, text="刷新", command=self.refresh, bg="#2563eb", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), padx=18).pack(side="left", padx=4)
        tk.Button(actions, text="工单历史 / WO HISTORY", command=self.open_history,
                  bg="#7c3aed", fg="white", font=("Microsoft YaHei UI", 11, "bold"), padx=18).pack(side="left", padx=4)
        tk.Button(actions, text="策略配置", command=self.open_config, bg="#7c3aed", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), padx=18).pack(side="left", padx=4)
        self.send_button = tk.Button(
            actions, text="手动发送NG / SEND NG",
            command=self.send_selected, bg="#d97706", activebackground="#b45309", fg="white",
            font=("Microsoft YaHei UI", 11, "bold"), padx=18,
        )
        self.send_button.pack(side="left", padx=4)
        self.return_button = tk.Button(actions, text="维修复活收单 / REPAIR RETURN RECEIPT",
                  command=self.receive_selected, bg="#059669", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), padx=18)
        self.return_button.pack(side="left", padx=4)
        self.status = tk.StringVar(value="正在读取 MES…")
        tk.Label(actions, textvariable=self.status, bg="#07111f", fg="#7dd3fc",
                 font=("Microsoft YaHei UI", 10, "bold")).pack(side="right")
        self.repair_heartbeat = tk.Label(actions, text="♥ ONLINE · REPAIR HEARTBEAT", bg="#07111f", fg="#22c55e",
                                         font=("Segoe UI", 10, "bold"))
        # Keep the heartbeat in the action row instead of overlaying status or
        # language controls.
        self.repair_heartbeat.pack(side="right", padx=(12, 0))
        self.repair_heartbeat.configure(text="\u2665 ONLINE \u00b7 REPAIR HEARTBEAT", width=25, anchor="e")
        self._repair_heartbeat_phase = False
        self.root.after(800, self._pulse_repair_heartbeat)
        book = ttk.Notebook(self.window); book.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        ng_tab = tk.Frame(book, bg="#0f172a"); return_tab = tk.Frame(book, bg="#0f172a")
        book.add(ng_tab, text="确认NG / SEND TO REPAIR"); book.add(return_tab, text="维修复活收单 / REPAIR RETURN")
        self.ng_tree = self._tree(ng_tab, (("sn","SN",230),("batch","批次",180),("reason","NG原因",260),("detected","发现时间",180),("sla","30分钟SLA",150)))
        self.return_tree = self._tree(return_tab, (("id","交接单",100),("batch","批次/SN",220),("source","来源",150),("status","状态",150),("sent","送出时间",190),("sla","收单状态",180)))
        self.refresh()

    def _pulse_repair_heartbeat(self):
        if not self.repair_heartbeat.winfo_exists():
            return
        self._repair_heartbeat_phase = not self._repair_heartbeat_phase
        self.repair_heartbeat.configure(fg="#86efac" if self._repair_heartbeat_phase else "#22c55e")
        self.root.after(800, self._pulse_repair_heartbeat)

    @staticmethod
    def _tree(parent, columns):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        table = tk.Frame(parent, bg="#0f172a")
        table.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        table.grid_rowconfigure(0, weight=1)
        table.grid_columnconfigure(0, weight=1)
        keys = tuple(item[0] for item in columns)
        tree = ttk.Treeview(table, columns=keys, show="headings", selectmode="browse")
        for key, title, width in columns:
            tree.heading(key, text=title); tree.column(key, width=width, anchor="center")
        y_scroll = ttk.Scrollbar(table, orient="vertical", command=tree.yview)
        x_scroll = ttk.Scrollbar(table, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        return tree

    @staticmethod
    def _millis(value):
        if isinstance(value, (int, float)):
            return int(value * 1000 if value < 10_000_000_000 else value)
        if not value: return int(time.time() * 1000)
        try: return int(datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp() * 1000)
        except Exception: return int(time.time() * 1000)

    @staticmethod
    def _clock(ms):
        if not ms: return "--"
        try: return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
        except Exception: return str(ms)

    def refresh(self):
        if self.preview:
            self.policy = dict(DEFAULT_REPAIR_POLICY)
            self.policy_summary.set("预览模式 · 30分钟SLA · 所有写入已阻止")
            self.ng_tree.delete(*self.ng_tree.get_children()); self.ng_rows.clear()
            sample = {"sn": "RJ-A7-PREVIEW-NG-0001", "batchId": "PREVIEW-BATCH-01",
                      "ngReason": "预览：组装ATE电阻测试失败", "firstDetectedAt": int(time.time() * 1000) - 8 * 60 * 1000}
            self.ng_rows["ng-preview"] = sample
            self.ng_tree.insert("", "end", iid="ng-preview", values=(sample["sn"], sample["batchId"], sample["ngReason"], self._clock(sample["firstDetectedAt"]), "22:00"))
            self.return_tree.delete(*self.return_tree.get_children()); self.return_rows.clear()
            self.return_rows["return-preview"] = {"transferId": "PREVIEW-RETURN-01", "batchId": sample["batchId"], "sourceStation": "manu_rework", "status": "WAITING_RECEIPT", "sentAt": "2026-08-04 15:00:00"}
            self.return_tree.insert("", "end", iid="return-preview", values=("PREVIEW-RETURN-01", sample["batchId"], "manu_rework", "WAITING_RECEIPT", "2026-08-04 15:00:00", "待读取"))
            self.status.set("UI预览 · 维修闭环可见 · 所有操作已禁用")
            return
        try:
            buckets = _json_request(self.base + "/api/station/bucket-snapshots").get("items", [])
            self.policy = _repair_policy(buckets, self.station_code)
            mode = self.policy["actionMode"]
            sla_minutes = self.policy["slaMinutes"]
            instruction = str(self.policy.get("instruction") or "")
            self.policy_summary.set(f"{mode} · {sla_minutes}分钟SLA · {instruction}")
            confirmed = []
            for bucket in buckets:
                if str(bucket.get("stationCode", "")).lower() == self.station_code and bucket.get("bucketName") == "confirmed_ng":
                    confirmed.extend(bucket.get("payload") or [])
            self.ng_tree.delete(*self.ng_tree.get_children()); self.ng_rows.clear()
            now = int(time.time() * 1000)
            for index, row in enumerate(confirmed):
                sn = str(row.get("sn") or row.get("ngSn") or "").upper()
                if not sn: continue
                detected = self._millis(row.get("firstDetectedAt") or row.get("ngDetectedAt") or row.get("testTime") or row.get("time"))
                remaining = sla_minutes * 60 - max(0, (now - detected) // 1000)
                sla = "已超时" if remaining < 0 else f"{remaining//60:02d}:{remaining%60:02d}"
                iid = f"ng-{index}"; self.ng_rows[iid] = row
                self.ng_tree.insert("", "end", iid=iid, values=(sn, row.get("batchId") or sn,
                    row.get("ngReason") or row.get("defectDescription") or row.get("errorCode") or "NG",
                    self._clock(detected), sla))
            query = urllib.parse.urlencode({"stationCode": self.station_code})
            handovers = _json_request(self.base + "/api/station/handovers?" + query).get("items", [])
            returns = [row for row in handovers if str(row.get("destinationType", "")).upper() == "REPAIR_RETURN"
                       and str(row.get("sourceStation", "")).lower() in {"manu_rework", "maintenance", "repair", "repair_center"}]
            self.return_tree.delete(*self.return_tree.get_children()); self.return_rows.clear()
            for index, row in enumerate(returns):
                iid = f"return-{index}"; self.return_rows[iid] = row
                self.return_tree.insert("", "end", iid=iid, values=(row.get("transferId", ""), row.get("batchId", ""),
                    row.get("sourceStation", ""), row.get("status", ""), row.get("sentAt", ""),
                    "待扫码收单" if row.get("status") == "WAITING_RECEIPT" else "已收单"))
            self.status.set(f"待送修 {len(confirmed)} · 待复活收单 {sum(r.get('status') == 'WAITING_RECEIPT' for r in returns)}")
            ready, reason = _dispatch_readiness(self.policy, confirmed, now)
            dispatch_allowed = bool(self.policy.get("allowRepairDispatch", True))
            self.send_button.configure(state="normal" if ready and dispatch_allowed else "disabled")
            self.status.set(("可派修 · " if ready else "等待触发 · ") + reason)
            if not dispatch_allowed:
                self.status.set(str(self.policy.get("instruction") or "本站维修送出由专用流程执行"))
        except Exception as exc:
            self.status.set("MES读取失败: " + str(exc)[:100])

    def open_history(self):
        """Read-only shared-component history surface for the current station."""
        win = tk.Toplevel(self.window)
        win.title(f"{self.station_name} · WO HISTORY / 维修工单历史")
        win.geometry("1180x680")
        win.configure(bg="#07111f")
        flow = tk.Canvas(win, height=120, bg="#07111f", highlightthickness=0)
        flow.pack(fill="x", padx=12, pady=(4, 8))
        flow_nodes = ("WO\nINFORM", "SUPERVISER\nACK", "SEND\nREPAIR", "REPAIRING",
                      "CALL\nPICKUP", "SEND\nSOURCE", "REVIVED")
        flow_boxes = []
        for index, label in enumerate(flow_nodes):
            x = 78 + index * 165
            if index:
                flow.create_line(x - 72, 58, x - 46, 58, fill="#64748b", width=2, arrow=tk.LAST)
            box = flow.create_rectangle(x - 64, 30, x + 64, 86, fill="#1e293b", outline="#475569", width=2)
            flow.create_text(x, 58, text=label, fill="#e2e8f0", font=("Segoe UI", 9, "bold"), justify="center")
            flow_boxes.append(box)
        flow_status = flow.create_text(78, 105, anchor="w", text="Select a WO to show its current node / 选择工单查看当前节点",
                                       fill="#94a3b8", font=("Segoe UI", 9))
        text = tk.Text(win, wrap="word", bg="#07111f", fg="#e2e8f0", font=("Consolas", 10))
        text.pack(fill="both", expand=True, padx=12, pady=12)
        # MES-owned latest-ten WO table.  The detail pane below remains the
        # append-only evidence view, so selecting a row never loses history.
        table = ttk.Treeview(win, columns=("time", "id", "batch", "station", "sn", "qty", "status", "cycle", "batchTime"),
                             show="headings", height=10)
        for key, label, width in (("time", "TIME / 时间", 170), ("id", "WO ID", 190),
                                  ("station", "STATION / 工站", 140), ("sn", "SN", 180),
                                  ("qty", "QTY / 数量", 80), ("status", "STATUS / 状态", 180)):
            table.heading(key, text=label); table.column(key, width=width, anchor="w")
        table.heading("batch", text="BATCH / 批次"); table.column("batch", width=150, anchor="w")
        table.heading("batchTime", text="BATCH TIME / 批次耗时"); table.column("batchTime", width=150, anchor="w")
        table.heading("cycle", text="CYCLE / 流程节点"); table.column("cycle", width=180, anchor="w")
        table.pack(fill="x", padx=12, pady=(0, 8), before=text)
        latest_wos = []
        try:
            query = urllib.parse.urlencode({"stationCode": self.station_code, "limit": 10})
            payload = _json_request(self.base + "/api/repair-station/work-orders?" + query)
            latest_wos = list(payload.get("items", payload.get("workOrders", [])) or [])[:10]
            for remote_row in latest_wos:
                # Cache MES facts locally; MES remains the authority for status.
                upsert_work_order(self.station_code, remote_row)
        except Exception as exc:
            try:
                latest_wos = latest_work_orders(self.station_code, 10)
            except Exception:
                latest_wos = []
            if latest_wos:
                pass
            elif self.preview:
                # Preview-only fixture: visible for UI smoke testing, never
                # persisted and never sent to MES/SQLite.
                statuses = ("CREATED", "WAITING_REPAIR", "REPAIR_RECEIVED", "REPAIR_IN_PROGRESS",
                            "REPAIR_COMPLETED", "RETURN_PENDING", "CLOSED_RETEST_PASS", "REPAIR_IN_PROGRESS",
                            "RETURN_PENDING", "CLOSED_RETEST_PASS")
                members = [{"sn": f"ISO-SN-{index:03d}", "workOrderNo": f"ISO-WO-{index:03d}",
                            "status": statuses[index - 1]} for index in range(1, 11)]
                latest_wos = [{"repairWorkOrderNo": f"ISO-WO-{index:03d}", "sn": f"ISO-SN-{index:03d}",
                               "batchId": "ISO-BATCH-001", "sourceStation": self.station_code,
                               "status": statuses[index - 1], "quantity": 1,
                               "issuedAt": "2026-08-08T01:00:00Z", "batchStartedAt": "2026-08-08T01:00:00Z",
                               "batchLastUpdatedAt": "2026-08-08T01:30:00Z", "batchMembers": members}
                              for index in range(1, 8)]
                # Explicitly surface the isolated 3-NG send simulation in the
                # history view.  These rows are preview-only and are never
                # persisted to MES or the station SQLite database.
                latest_wos = [{"repairWorkOrderNo": f"SIM-RW-{index:03d}",
                               "eventId": f"SIM-EVENT-{index:03d}",
                               "sn": f"SIM-MB-{index:03d}", "batchId": "SIM-NG-BATCH-001",
                               "sourceStation": self.station_code, "sourceProcessDomain": self.process_domain,
                               "sourceLineCode": self.line_code, "destinationStation": "repair_station",
                               "status": "WAITING_REPAIR", "quantity": 1,
                               "managerNotice": "PENDING_PICKUP_ACK",
                               "issuedAt": "2026-08-08T05:00:00Z", "sentToRepairAt": "2026-08-08T05:00:01Z",
                               "batchStartedAt": "2026-08-08T05:00:00Z",
                               "batchLastUpdatedAt": "2026-08-08T05:00:01Z",
                               "batchMembers": [{"sn": f"SIM-MB-{index:03d}",
                                                 "workOrderNo": f"SIM-RW-{index:03d}",
                                                 "status": "WAITING_REPAIR"}]}
                              for index in (2, 5, 8)] + latest_wos
            else:
                latest_wos = [{"status": "OFFLINE", "error": str(exc)}]
        for row in latest_wos:
            status = str(row.get("status") or "-").upper()
            cycle = {"CREATED": "CREATED / 已创建", "WAITING_REPAIR": "REPAIR_RECEIVED / 待接收",
                     "REPAIR_IN_PROGRESS": "IN_REPAIR / 维修中", "REPAIR_COMPLETED": "REPAIR_DONE / 已维修",
                     "RETURN_PENDING": "RETURNED / 待返回", "CLOSED_RETEST_PASS": "DONE / 已完成"}.get(status, status)
            batch_start = row.get("batchStartedAt") or row.get("issuedAt") or row.get("createdAt")
            batch_end = row.get("batchLastUpdatedAt") or row.get("updatedAt")
            batch_time = f"{batch_start or '-'} → {batch_end or '-'}"
            table.insert("", "end", values=(row.get("issuedAt") or row.get("createdAt") or row.get("updatedAt") or "-",
                row.get("repairWoId") or row.get("repairWorkOrderNo") or row.get("id") or "-",
                row.get("batchId") or "-",
                row.get("station") or row.get("sourceStation") or row.get("stationCode") or "-",
                row.get("sn") or row.get("serialNumber") or "-",
                row.get("quantity", row.get("qty", "-")), status, cycle, batch_time))
        def show_wo_detail(_event=None):
            selected = table.selection()
            if not selected: return
            detail = latest_wos[table.index(selected[0])]
            projection = cycle_projection(detail)
            status = projection["status"]
            node_index = next((index for index, node in enumerate(projection["nodes"]) if node["active"]), 0)
            for index, box in enumerate(flow_boxes):
                flow.itemconfigure(box, fill="#2563eb" if index == node_index else "#1e293b",
                                   outline="#60a5fa" if index == node_index else "#475569")
            flow.itemconfigure(flow_status, text=f"CURRENT NODE / 当前节点: {flow_nodes[node_index].replace(chr(10), ' / ')} · status={status or '-'}")
            text.configure(state="normal"); text.delete("1.0", "end")
            timeline = [
                ("CREATED / 已创建", detail.get("createdAt") or detail.get("issuedAt")),
                ("REPAIR_RECEIVED / 回修站接收", detail.get("receivedAt")),
                ("IN_REPAIR / 维修中", detail.get("repairStartedAt")),
                ("REPAIR_DONE / 完成维修", detail.get("repairCompletedAt")),
                ("RETURNED / 已返回", detail.get("returnedAt")),
                ("DONE / 已完成", detail.get("closedAt") or detail.get("completedAt")),
            ]
            members = detail.get("batchMembers") or []
            member_text = "\n".join(f"  {item.get('sn','-')} | {item.get('workOrderNo','-')} | {item.get('status','-')}" for item in members)
            status_history = detail.get("statusHistory") or []
            status_text = "\n".join(
                f"  {item.get('occurredAt','-')} | {item.get('status','-')} | source={item.get('statusSource','-')}"
                for item in status_history
            ) or "  -"
            identity = (
                f"SN / 产品序列号: {detail.get('sn') or detail.get('serialNumber') or '-'}\n"
                f"SOURCE / 来源工站: {detail.get('sourceStation') or detail.get('station') or '-'}\n"
                f"DESTINATION / 目标回修站: {detail.get('destinationStation') or '-'}\n"
                f"QUANTITY / 数量: {detail.get('quantity') or detail.get('qty') or '-'}\n"
            )
            text.insert("1.0", identity + "\nWO CYCLE / 工单生命周期\n" + "\n".join(f"{name}: {value or '-'}" for name, value in timeline)
                       + "\n\nSTATUS HISTORY / MES 状态历史\n" + status_text
                       + "\n\nBATCH MEMBERS / 批次成员 SN\n" + (member_text or "  -")
                       + "\n\nDETAIL / 详细记录\n" + json.dumps(detail, ensure_ascii=False, indent=2, default=str)); text.configure(state="disabled")
        table.bind("<<TreeviewSelect>>", show_wo_detail)
        lines = [f"SHARED REPAIR {COMPONENT_VERSION}", f"STATION {self.station_code}", "", "ACTIVE NG / 当前 NG"]
        for row in self.ng_rows.values():
            lines.append(f"SN={row.get('sn') or row.get('ngSn','-')} | shipmentId={row.get('shipmentId','-')} | "
                         f"repairWoId={row.get('repairWoId') or row.get('repairWorkOrderNo','-')} | "
                         f"boxQr={row.get('boxQr') or row.get('stationQr','-')} | qty={row.get('quantity','-')}")
        lines.append("\nRETURNS / 维修返回")
        for row in self.return_rows.values():
            lines.append(f"transfer={row.get('transferId','-')} | shipmentId={row.get('shipmentId','-')} | "
                         f"repairWoId={row.get('repairWorkOrderNo','-')} | status={row.get('status','-')}")
        text.insert("1.0", "\n".join(lines)); text.configure(state="disabled")
        tk.Button(win, text="关闭 / CLOSE", command=win.destroy).pack(pady=(0, 12))

    def open_config(self):
        if self.preview:
            messagebox.showinfo("预览模式", "维修策略组件可见，但预览模式禁止修改MES配置。", parent=self.window)
            return
        win = tk.Toplevel(self.window)
        win.title(f"{self.station_name} · 维修策略配置")
        win.geometry("650x820")
        win.configure(bg="#0f172a")
        fields = {}
        rows = [
            ("时间阈值（分钟，可输入30/60/120/180或其他值）", "timeThresholdMinutes"),
            ("数量阈值（可输入10/15/20或其他值）", "quantityThreshold"),
            ("维修SLA（分钟）", "slaMinutes"),
            ("指定派修时间（HH:MM）", "designatedTime"),
            ("班末时间（HH:MM）", "shiftEndTime"),
            ("维修目的工站", "repairDestination"),
            ("最大复测次数（0表示禁止复测）", "maxRetestCount"),
            ("自动执行身份", "automaticActor"),
            ("现场特殊要求", "instruction"),
            ("升级报警分钟数", "escalationMinutes"),
            ("重复NG观察窗口（小时）", "repeatNgWindowHours"),
            ("重复NG升级次数", "repeatNgThreshold"),
            ("允许角色（逗号分隔）", "allowedRoles"),
            ("指定返修返回工站", "designatedReturnStation"),
            ("配置原因（必填）", "configReason"),
            ("生效时间（留空立即）", "effectiveFrom"),
        ]
        for label, key in rows:
            frame = tk.Frame(win, bg="#0f172a"); frame.pack(fill="x", padx=18, pady=5)
            tk.Label(frame, text=label, bg="#0f172a", fg="#cbd5e1", width=34, anchor="w").pack(side="left")
            raw = self.policy.get(key, "")
            value = tk.StringVar(value=",".join(raw) if isinstance(raw, list) else str(raw)); fields[key] = value
            tk.Entry(frame, textvariable=value, width=22).pack(side="right")
        timing = tk.StringVar(value=self.policy.get("dispatchTiming", "ANY_TIME")); fields["dispatchTiming"] = timing
        tf = tk.Frame(win, bg="#0f172a"); tf.pack(fill="x", padx=18, pady=8)
        tk.Label(tf, text="派修时机", bg="#0f172a", fg="#cbd5e1", width=34, anchor="w").pack(side="left")
        ttk.Combobox(tf, textvariable=timing, values=("ANY_TIME", "DESIGNATED_TIME", "END_OF_SHIFT"), state="readonly", width=20).pack(side="right")
        mode = tk.StringVar(value=self.policy.get("actionMode", "SEND_REPAIR")); fields["actionMode"] = mode
        mf = tk.Frame(win, bg="#0f172a"); mf.pack(fill="x", padx=18, pady=8)
        tk.Label(mf, text="NG动作模式", bg="#0f172a", fg="#cbd5e1", width=34, anchor="w").pack(side="left")
        ttk.Combobox(mf, textvariable=mode, values=("SEND_REPAIR", "MARK_ONLY", "REMOVE_IMMEDIATELY"), state="readonly", width=20).pack(side="right")
        dispatch_mode = tk.StringVar(value=str(self.policy.get("dispatchMode") or "AUTOMATIC")); fields["dispatchMode"] = dispatch_mode
        df = tk.Frame(win, bg="#0f172a"); df.pack(fill="x", padx=18, pady=8)
        tk.Label(df, text="执行模式", bg="#0f172a", fg="#cbd5e1", width=34, anchor="w").pack(side="left")
        ttk.Combobox(df, textvariable=dispatch_mode, values=("AUTOMATIC", "MANUAL"), state="readonly", width=20).pack(side="right")
        for label, key, choices in (
            ("优先级", "priority", ("NORMAL", "HIGH", "CRITICAL")),
            ("返修返回规则", "returnStationMode", ("ORIGIN", "DESIGNATED")),
            ("MES离线策略", "offlinePolicy", ("BLOCK", "READ_ONLY")),
        ):
            line = tk.Frame(win, bg="#0f172a"); line.pack(fill="x", padx=18, pady=5)
            tk.Label(line, text=label, bg="#0f172a", fg="#cbd5e1", width=34, anchor="w").pack(side="left")
            var = tk.StringVar(value=str(self.policy.get(key, choices[0]))); fields[key] = var
            ttk.Combobox(line, textvariable=var, values=choices, state="readonly", width=20).pack(side="right")
        flags = tk.Frame(win, bg="#0f172a"); flags.pack(fill="x", padx=18, pady=8)
        for label, key in (("启用", "enabled"), ("QC审批", "qcApprovalRequired"),
                           ("线长审批", "lineLeaderApprovalRequired"), ("维修证据", "evidenceRequired"),
                           ("允许返修收单", "allowRepairReturn")):
            var = tk.BooleanVar(value=bool(self.policy.get(key, False))); fields[key] = var
            tk.Checkbutton(flags, text=label, variable=var, bg="#0f172a", fg="#e2e8f0",
                           selectcolor="#1e293b", activebackground="#0f172a").pack(side="left", padx=5)
        def save():
            try:
                updated = dict(self.policy)
                for key, value in fields.items():
                    raw = value.get()
                    updated[key] = raw.strip() if isinstance(raw, str) else raw
                for key in ("timeThresholdMinutes", "quantityThreshold", "slaMinutes", "escalationMinutes", "repeatNgWindowHours", "repeatNgThreshold"):
                    updated[key] = max(1, int(updated[key]))
                updated["maxRetestCount"] = max(0, int(updated["maxRetestCount"]))
                updated["allowedRoles"] = [item.strip().upper() for item in str(updated.get("allowedRoles") or "").split(",") if item.strip()]
                if not str(updated.get("configReason") or "").strip():
                    raise ValueError("配置原因必须填写，确保所有口径事出有因")
                updated = _repair_policy([{"stationCode": self.station_code, "bucketName": "repair_policy", "payload": updated}], self.station_code)
                domain = "auto" if self.station_code.startswith("auto_") else "manual"
                url = self.base + "/api/station/bucket-snapshots/" + urllib.parse.quote(self.station_code) + "/repair_policy"
                _json_request(url, "PUT", {"payload": updated, "domain": domain})
                self.policy = updated; win.destroy(); self.refresh()
                messagebox.showinfo("配置已保存", "MES 已更新本站维修策略。", parent=self.window)
            except Exception as exc:
                messagebox.showerror("配置保存失败", str(exc), parent=win)
        tk.Button(win, text="保存到 MES", command=save, bg="#16a34a", fg="white",
                  font=("Microsoft YaHei UI", 12, "bold"), padx=28, pady=8).pack(pady=18)

    def send_selected(self):
        if self.preview:
            messagebox.showinfo("预览模式", "维修闭环组件可见，但预览模式禁止生成维修工单。", parent=self.window)
            return
        if not _routing_available(self.route_graph):
            messagebox.showerror("MES路由不可用", "未读取到有效的MES已发布NG路由，禁止本地决定维修去向。", parent=self.window)
            return
        if not self.policy.get("allowRepairDispatch", True):
            messagebox.showwarning(
                "禁止直接送修",
                str(self.policy.get("instruction") or "本站维修送出由专用流程执行，禁止从此监控组件重复建单。"),
                parent=self.window,
            )
            return
        selected = self.ng_tree.selection()
        if not selected: messagebox.showwarning("请选择NG", "请先选择需要送修的确认NG记录", parent=self.window); return
        row = self.ng_rows[selected[0]]
        sn = str(row.get("sn") or row.get("ngSn") or "").upper()
        actor = simpledialog.askstring("确认人", "请输入操作员/QC工号：", parent=self.window)
        if self.policy.get("requireOperator", True) and not actor: return
        actor = actor or "STATION_AGENT"
        role = simpledialog.askstring("确认角色", "请输入角色：OPERATOR / QC / LINE_LEADER", initialvalue="OPERATOR", parent=self.window)
        role = str(role or "OPERATOR").strip().upper()
        allowed = [str(item).upper() for item in self.policy.get("allowedRoles") or []]
        if allowed and role not in allowed:
            messagebox.showerror("角色无权限", f"{role} 不在允许角色中：{', '.join(allowed)}", parent=self.window); return
        mode = self.policy["actionMode"]
        sla_minutes = self.policy["slaMinutes"]
        prompt = {"SEND_REPAIR": "确认NG并送往回修站？", "MARK_ONLY": "确认NG并仅标记报警？",
                  "REMOVE_IMMEDIATELY": "确认NG并要求现场立即取出？"}[mode]
        if not messagebox.askyesno("执行NG策略", f"{prompt}\nSN: {sn}\nSLA: {sla_minutes}分钟", parent=self.window): return
        detected = self._millis(row.get("firstDetectedAt") or row.get("ngDetectedAt") or row.get("testTime") or row.get("time"))
        payload = {"processDomain": self.process_domain, "lineCode": self.line_code,
                   "eventId": f"{self.station_code}:REPAIR_DISPATCH:{row.get('batchId') or sn}:{sn}",
                   "sourceStation": self.station_code, "sourceStationName": self.station_name,
                   "sourceProcessDomain": self.process_domain, "sourceLineCode": self.line_code,
                   "ngSn": sn, "batchId": row.get("batchId") or sn, "members": [row],
                   "firstDetectedAt": detected, "repairDeadlineAt": detected + sla_minutes * 60 * 1000,
                   "confirmedBy": actor, "confirmedRole": role, "submittedBy": actor,
                   "clickedAt": int(time.time() * 1000), "actionMode": mode,
                   "repairDestination": self.policy.get("repairDestination") or "manu_rework",
                   "maxRetestCount": int(self.policy.get("maxRetestCount") or 0),
                   "routePolicyVersion": self.policy.get("version") or self.policy.get("policyVersion") or "",
                   **_routing_metadata(self.route_graph),
                   "stationInstruction": self.policy.get("instruction") or "",
                   "priority": self.policy.get("priority") or "NORMAL",
                   "qcApprovalRequired": bool(self.policy.get("qcApprovalRequired")),
                   "lineLeaderApprovalRequired": bool(self.policy.get("lineLeaderApprovalRequired")),
                   "returnStationMode": self.policy.get("returnStationMode") or "ORIGIN",
                   "designatedReturnStation": self.policy.get("designatedReturnStation") or "",
                   "evidenceRequired": bool(self.policy.get("evidenceRequired")),
                   "policyReason": self.policy.get("configReason") or ""}
        payload.update(_ng_loop_metadata(self.policy, actor, "DEPLOYMENT"))
        try:
            reply = _json_request(self.base + "/api/station/maintenance-handovers", "POST", payload)
            messagebox.showinfo("NG策略已执行", f"模式：{mode}\n维修工单：{reply.get('repairWorkOrderNo','')}\n交接单：{reply.get('billNo','')}\n{sla_minutes}分钟SLA已开始", parent=self.window)
            self.refresh()
        except Exception as exc: messagebox.showerror("送修失败", str(exc), parent=self.window)

    def receive_selected(self):
        if self.preview:
            messagebox.showinfo("预览模式", "维修返回组件可见，但预览模式禁止执行复活收单。", parent=self.window)
            return
        selected = self.return_tree.selection()
        if not selected: messagebox.showwarning("请选择复活单", "请先选择维修复活交接单", parent=self.window); return
        row = self.return_rows[selected[0]]
        if row.get("status") != "WAITING_RECEIPT": messagebox.showinfo("已经收单", "该复活交接单已完成", parent=self.window); return
        actor = simpledialog.askstring("收单人", "请扫描或输入接收人工号：", parent=self.window)
        if not actor: return
        payload = {"processDomain": self.process_domain, "lineCode": self.line_code,
                   "eventId": f"{self.station_code}:REPAIR_RETURN_RECEIVE:{row.get('batchId') or ''}",
                   "action": "ACCEPT_TRANSFER", "sourceStationCode": row.get("sourceStation") or "manu_rework",
                   "destinationStationCode": self.station_code, "batchId": row.get("batchId"), "acceptedBy": actor}
        try:
            _json_request(self.base + "/api/station/operator-command", "POST", payload)
            messagebox.showinfo("复活收单完成", "维修返回已接收；请按工艺要求执行授权复测。", parent=self.window)
            self.refresh()
        except Exception as exc: messagebox.showerror("复活收单失败", str(exc), parent=self.window)


def install_repair_workflow(root, station_code, mes_base_url, station_name="", preview=False):
    panel = RepairWorkflowPanel(root, station_code, mes_base_url, station_name, preview=preview)
    root._repair_workflow = panel
    return panel


def render_streamlit_repair_workflow(st, station_code, mes_base_url, station_name=""):
    """Render the same MES repair loop in Streamlit-based station agents."""
    code = str(station_code).strip().lower()
    process_domain, line_code = _process_context(code)
    base = str(mes_base_url).replace("/api/pda/events", "").rstrip("/")
    route_graph = _load_ng_routing_graph()
    label = station_name or code
    now = time.monotonic()
    if now - _LAST_HEARTBEAT.get(code, 0) >= 10:
        try:
            _component_heartbeat(code, base)
            _LAST_HEARTBEAT[code] = now
        except Exception:
            pass
    with st.expander("维修闭环 / REPAIR CLOSED LOOP", expanded=False):
        try:
            buckets = _json_request(base + "/api/station/bucket-snapshots").get("items", [])
            policy = _repair_policy(buckets, code)
            with st.expander("策略配置 / POLICY", expanded=False):
                with st.form(f"repair-policy-{code}"):
                    time_minutes = st.number_input("时间阈值（分钟）", 1, 10080, int(policy["timeThresholdMinutes"]))
                    quantity = st.number_input("数量阈值", 1, 10000, int(policy["quantityThreshold"]))
                    timing = st.selectbox("派修时机", ("ANY_TIME", "DESIGNATED_TIME", "END_OF_SHIFT"), index=("ANY_TIME", "DESIGNATED_TIME", "END_OF_SHIFT").index(policy["dispatchTiming"]))
                    designated = st.text_input("指定时间 HH:MM", str(policy.get("designatedTime") or "15:00"))
                    shift_end = st.text_input("班末时间 HH:MM", str(policy.get("shiftEndTime") or "17:00"))
                    sla = st.number_input("维修SLA（分钟）", 1, 10080, int(policy["slaMinutes"]))
                    escalation = st.number_input("升级报警（分钟）", 1, 10080, int(policy["escalationMinutes"]))
                    action_mode = st.selectbox("NG动作", ("SEND_REPAIR", "MARK_ONLY", "REMOVE_IMMEDIATELY"), index=("SEND_REPAIR", "MARK_ONLY", "REMOVE_IMMEDIATELY").index(policy["actionMode"]))
                    destination = st.text_input("维修目的工站", str(policy.get("repairDestination") or "manu_rework"))
                    instruction = st.text_input("现场特殊要求", str(policy.get("instruction") or ""))
                    reason = st.text_input("配置原因（必填）", str(policy.get("configReason") or ""))
                    save_policy = st.form_submit_button("保存到 MES")
                if save_policy:
                    if not reason.strip():
                        st.error("配置原因必须填写")
                    else:
                        updated = dict(policy)
                        updated.update({"timeThresholdMinutes": int(time_minutes), "quantityThreshold": int(quantity),
                                        "dispatchTiming": timing, "designatedTime": designated, "shiftEndTime": shift_end,
                                        "slaMinutes": int(sla), "escalationMinutes": int(escalation),
                                        "actionMode": action_mode, "repairDestination": destination,
                                        "instruction": instruction, "configReason": reason})
                        domain = "auto" if code.startswith("auto_") else "manual"
                        url = base + "/api/station/bucket-snapshots/" + urllib.parse.quote(code) + "/repair_policy"
                        _json_request(url, "PUT", {"payload": updated, "domain": domain})
                        st.success("策略已保存到 MES")
            if not policy.get("enabled", True):
                st.info("MES 已停用本站维修操作；NG仍保留追溯。")
                return
            rows = []
            for bucket in buckets:
                if str(bucket.get("stationCode", "")).lower() == code and bucket.get("bucketName") == "confirmed_ng":
                    rows.extend(bucket.get("payload") or [])
            mode = policy["actionMode"]
            sla_minutes = policy["slaMinutes"]
            st.caption(f"{label} · {mode} · {sla_minutes}分钟SLA · {policy.get('instruction') or ''}")
            if not rows:
                st.success("当前没有待送修的确认 NG")
                return
            ready, readiness_reason = _dispatch_readiness(policy, rows)
            st.info(f"MES 批次规则 / BATCH RULE: {readiness_reason}")
            if not ready:
                st.warning("尚未达到 MES 规定的数量/时间/派修时机，暂不生成维修工单。")
                return
            options = {}
            for row in rows:
                sn = str(row.get("sn") or row.get("ngSn") or "").upper()
                if sn:
                    options[f"{sn} · {row.get('ngReason') or row.get('errorCode') or 'NG'}"] = row
            selected = st.selectbox("选择确认 NG", list(options), key=f"repair-ng-{code}")
            actor = st.text_input("操作员/QC工号", key=f"repair-actor-{code}")
            action_label = {"SEND_REPAIR": "确认NG并送往回修站", "MARK_ONLY": "确认NG（仅标记/报警）",
                            "REMOVE_IMMEDIATELY": "确认NG并立即取出"}[mode]
            batch_selected = [selected] if selected else []
            if st.button(action_label, type="primary", key=f"repair-send-{code}"):
                if batch_selected:
                    selected_row = options[batch_selected[0]]
                    selected_sn = str(selected_row.get("sn") or selected_row.get("ngSn") or "").upper()
                    selected_index = next((i for i, item in enumerate(rows)
                                           if str(item.get("sn") or item.get("ngSn") or "").upper() == selected_sn), 0)
                    batch_limit = max(1, int(policy.get("quantityThreshold") or 1))
                    batch_start = (selected_index // batch_limit) * batch_limit
                    batch_rows = rows[batch_start:batch_start + batch_limit]
                    row = dict(batch_rows[0])
                    row["members"] = batch_rows
                    row["quantity"] = len(batch_rows)
                    row["batchId"] = row.get("batchId") or f"NG-BATCH-{int(time.time() * 1000)}"
                    options[batch_selected[0]] = row
                    selected = batch_selected[0]
                if not _routing_available(route_graph):
                    st.error("未读取到有效的MES已发布NG路由，禁止本地决定维修去向。")
                    return
                if not actor.strip():
                    st.error("必须输入操作员/QC工号")
                else:
                    row = options[selected]
                    sn = str(row.get("sn") or row.get("ngSn") or "").upper()
                    detected = RepairWorkflowPanel._millis(row.get("firstDetectedAt") or row.get("ngDetectedAt") or row.get("testTime") or row.get("time"))
                    payload = {"processDomain": process_domain, "lineCode": line_code,
                               "eventId": f"{code}:REPAIR_DISPATCH:{row.get('batchId') or sn}:{sn}",
                               "sourceStation": code, "sourceStationName": label, "ngSn": sn,
                               "batchId": row.get("batchId") or sn, "members": row.get("members") or [row], "quantity": row.get("quantity") or 1,
                               "firstDetectedAt": detected, "repairDeadlineAt": detected + sla_minutes * 60 * 1000,
                               "confirmedBy": actor.strip(), "confirmedRole": "OPERATOR",
                               "submittedBy": actor.strip(), "clickedAt": int(time.time() * 1000),
                               "actionMode": mode,
                               "repairDestination": policy.get("repairDestination") or "manu_rework",
                               **_routing_metadata(_load_ng_routing_graph()),
                               "stationInstruction": policy.get("instruction") or ""}
                    reply = _json_request(base + "/api/station/maintenance-handovers", "POST", payload)
                    st.success(f"维修工单已激活：{reply.get('repairWorkOrderNo') or reply.get('billNo') or sn}")
        except Exception as exc:
            st.error("MES维修闭环读取失败：" + str(exc))
