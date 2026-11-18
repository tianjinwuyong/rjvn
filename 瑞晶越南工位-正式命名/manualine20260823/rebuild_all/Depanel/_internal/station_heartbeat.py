# -*- coding: utf-8 -*-
"""Small, non-blocking heartbeat shared by manual-line station agents."""
import json
import threading
import time
import urllib.request

from station_domain import apply_line_domain
from station_common_agent import build_common_agent


class StationHeartbeat:
    def __init__(self, station_code, mes_events_url, agent_name, interval=10):
        self.station_code = station_code
        self.url = mes_events_url
        self.agent_name = agent_name
        self.interval = max(3, int(interval))
        # The heartbeat is the common-agent bridge used by every production
        # launcher. It adds shared identity/module metadata without taking over
        # station-specific equipment behavior or MES decisions.
        self.common_agent = build_common_agent(
            station_code,
            line_domain="AUTO_LINE",
            mes_base_url=mes_events_url,
            equipment_adapter=agent_name,
        )
        self.machine_qr = self.common_agent.identity()["machineQr"]
        self._last_attempt = 0.0
        self._lock = threading.Lock()

    def tick(self, **status):
        now = time.monotonic()
        with self._lock:
            if now - self._last_attempt < self.interval:
                return False
            self._last_attempt = now
        payload = apply_line_domain({
            "type": "AGENT_HEARTBEAT",
            "stationCode": self.station_code,
            "payload": {
                "agent": self.agent_name,
                "machineQr": self.machine_qr,
                "commonAgent": self.common_agent.identity(),
                "status": "running",
                "timestamp": int(time.time() * 1000),
                **status,
            },
        }, self.station_code)
        try:
            request = urllib.request.Request(
                self.url, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                {"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=3) as response:
                response.read()
            return True
        except Exception:
            return False

