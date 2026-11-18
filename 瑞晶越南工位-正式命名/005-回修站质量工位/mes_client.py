# -*- coding: utf-8 -*-
"""
mes_client.py — MES Web API Integration for Station Agents
工位 Agent → MES Web 数据通路

功能:
  1. 工位心跳上报（POST /mes/heartbeat/:stationCode）— 无需认证
  2. 工位事件推送（POST /mes/events）— 需 JWT（mes.execute）
  3. MES 配置拉取（防呆规则、工艺路线）— 需 JWT
  4. 自动登录获取 Token（用 service account）

数据流:
  Station Agent (Python)                    MES API (Express :8080)
      │                                           │
      │ ① 登录获取 Token                           │
      │ POST /auth/login  →                      │
      │ ← { token }                              │
      │                                           │
      │ ② 每 30s 心跳上报                          │
      │ POST /mes/heartbeat/{stationCode}  →     │
      │                                           │
      │ ③ NG/产出事件推送                           │
      │ POST /mes/events (Bearer Token)  →        │
      │                                           │
      │ ④ 配置拉取                                  │
      │ GET /mes/fool-proof-rules  →              │

用法:
  from mes_client import MesClient
  client = MesClient(
      mes_url="http://192.168.1.100:8080",
      station_code="ICT-01",
      line_code="AUTO-LINE",
      username="VN_OP_001",
      password="Factory@123",
  )
  client.start()           # 开始心跳
  client.push_event(       # 推送事件
      pcbSerial="...",
      eventType="scan_out",
      result="PASS",
      operator="VN_OP_001",
  )
  client.stop()            # 停止
"""

import json
import logging
import os
import threading
import time
import urllib.parse
import urllib.request
import urllib.error

logger = logging.getLogger("mes_client")

# 默认心跳间隔（秒）
_DEFAULT_HEARTBEAT_INTERVAL = 30


class MesClient:
    """MES API 客户端 — 工位心跳 + 事件推送"""

    def __init__(
        self,
        mes_url: str = "",
        station_code: str = "",
        line_code: str = "",
        username: str = "",
        password: str = "",
        heartbeat_interval: int = _DEFAULT_HEARTBEAT_INTERVAL,
        auto_start: bool = False,
    ):
        self.mes_url = mes_url.rstrip("/")
        self.station_code = station_code
        self.line_code = line_code
        self.username = username
        self.password = password
        self.heartbeat_interval = heartbeat_interval

        self._token = None
        self._token_expires_at = 0
        self._running = False
        self._thread = None
        self._station_name_cn = ""  # 中文名称

        if auto_start:
            self.start()

    # ── 公共接口 ─────────────────────────────────────────────────────

    def start(self):
        """启动心跳线程"""
        if self._running:
            return
        if not self.mes_url:
            logger.warning("[mes_client] mes_url 未配置，不启动")
            return
        if not self.station_code:
            logger.warning("[mes_client] station_code 未配置，不启动")
            return

        self._running = True
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        logger.info(
            f"[mes_client] 已启动: {self.station_code} → {self.mes_url}"
        )

    def stop(self):
        """停止心跳线程"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("[mes_client] 已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    def push_event(
        self,
        pcb_serial: str = "",
        event_type: str = "scan_out",
        result: str = "PASS",
        machine_code: str = "",
        operator: str = "",
        trace_key: str = "",
    ) -> bool:
        """推送工位事件到 MES

        POST /mes/events  { payload: { stationCode, pcbSerial, eventType, result, ... } }

        Returns:
            True 表示发送成功（HTTP 2xx）
        """
        payload = {
            "stationCode": self.station_code,
            "pcbSerial": pcb_serial,
            "eventType": event_type,
            "result": result,
        }
        if machine_code:
            payload["machineCode"] = machine_code
        if operator:
            payload["operator"] = operator
        if trace_key:
            payload["traceKey"] = trace_key

        body = json.dumps({"payload": payload}, ensure_ascii=False).encode("utf-8")
        token = self._ensure_token()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            req = urllib.request.Request(
                f"{self.mes_url}/mes/events",
                data=body,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status < 300:
                    logger.info(
                        f"[mes_client] event OK: {event_type} {pcb_serial} → {result}"
                    )
                    return True
                else:
                    logger.warning(
                        f"[mes_client] event FAIL: HTTP {resp.status} {resp.read().decode()[:200]}"
                    )
                    return False
        except urllib.error.HTTPError as e:
            logger.warning(
                f"[mes_client] event HTTP {e.code}: {e.read().decode()[:200]}"
            )
            return False
        except Exception as e:
            logger.warning(f"[mes_client] event error: {e}")
            return False

    # ── 内部方法 ─────────────────────────────────────────────────────

    def _heartbeat_loop(self):
        """心跳线程主循环"""
        while self._running:
            try:
                self._send_heartbeat()
            except Exception as e:
                logger.warning(f"[mes_client] heartbeat error: {e}")
            # 等待，但每 5 秒检查一次是否要退出
            for _ in range(self.heartbeat_interval // 5):
                if not self._running:
                    return
                time.sleep(5)

    def _send_heartbeat(self):
        """发送一次心跳"""
        body = json.dumps(
            {
                "operator": self.username,
                "lineCode": self.line_code,
            },
            ensure_ascii=False,
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{self.mes_url}/mes/heartbeat/{urllib.parse.quote(self.station_code, safe='')}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status < 300:
                logger.debug(f"[mes_client] heartbeat OK: {self.station_code}")

    def _ensure_token(self) -> str:
        """获取有效 Token，过期则自动重新登录"""
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        return self._login()

    def _login(self) -> str:
        """登录 MES 获取 JWT Token"""
        if not self.username or not self.password:
            return ""
        try:
            body = json.dumps(
                {
                    "username": self.username,
                    "password": self.password,
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                f"{self.mes_url}/auth/login",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                # 响应格式: { ok: true, data: { token, expiresAt, user } }
                payload = data.get("data") or data
                self._token = payload.get("token", "")
                expires = payload.get("expiresAt", "")
                if expires:
                    try:
                        from datetime import datetime

                        exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                        self._token_expires_at = exp_dt.timestamp()
                    except Exception:
                        self._token_expires_at = time.time() + 3600
                logger.info(
                    f"[mes_client] 登录成功: {self.username}, token 有效期至 {expires}"
                )
                return self._token
        except urllib.error.HTTPError as e:
            logger.warning(
                f"[mes_client] 登录失败 HTTP {e.code}: {e.read().decode()[:200]}"
            )
        except Exception as e:
            logger.warning(f"[mes_client] 登录失败: {e}")
        return ""

    def __repr__(self):
        return (
            f"<MesClient station={self.station_code} "
            f"line={self.line_code} url={self.mes_url} "
            f"running={self._running}>"
        )


# ── 全局单例（方便 aoi_api_server.py 使用）────────────────────────────────

_GLOBAL_CLIENT: MesClient = None


def init(
    mes_url: str = "",
    station_code: str = "",
    line_code: str = "",
    username: str = "",
    password: str = "",
    auto_start: bool = True,
) -> MesClient:
    """初始化并启动全局 MES Client（幂等，重复调用返回同一实例）"""
    global _GLOBAL_CLIENT
    if _GLOBAL_CLIENT is not None and _GLOBAL_CLIENT.is_running:
        return _GLOBAL_CLIENT
    _GLOBAL_CLIENT = MesClient(
        mes_url=mes_url,
        station_code=station_code,
        line_code=line_code,
        username=username,
        password=password,
        auto_start=auto_start,
    )
    return _GLOBAL_CLIENT


def get_client() -> MesClient:
    """获取全局 MES Client 实例"""
    return _GLOBAL_CLIENT


def push_event(
    pcb_serial: str = "",
    event_type: str = "scan_out",
    result: str = "PASS",
    machine_code: str = "",
    operator: str = "",
    trace_key: str = "",
) -> bool:
    """通过全局 MES Client 推送事件（快捷方式）"""
    global _GLOBAL_CLIENT
    if _GLOBAL_CLIENT is None:
        logger.warning("[mes_client] 全局客户端未初始化，无法推送事件")
        return False
    return _GLOBAL_CLIENT.push_event(
        pcb_serial=pcb_serial,
        event_type=event_type,
        result=result,
        machine_code=machine_code,
        operator=operator,
        trace_key=trace_key,
    )
