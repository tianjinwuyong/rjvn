"""Canonical domain metadata for manual-line station agents."""

PROCESS_DOMAIN = "MANUAL_LINE"
LINE_CODE = "L004"
NUMERIC_LINE_CODE = "004"
LOCAL_INFO_API_VERSION = "v1"
LOCAL_INFO_API_READ_ONLY = True
LOCAL_INFO_PORT_BASE = 12100
LOCAL_INFO_PORT_RANGE = (12101, 12113)


def resolve_line_code(station_code=""):
    code = str(station_code or "").strip().upper()
    if not code.startswith(("MANU_", "MANUAL-", "MANU-")):
        raise ValueError(f"Manual-line station requires MANU station code: {station_code}")
    return LINE_CODE


def apply_line_domain(event, station_code=""):
    event = dict(event or {})
    event["lineCode"] = resolve_line_code(station_code or event.get("stationCode"))
    event["processDomain"] = PROCESS_DOMAIN
    event["numericLineCode"] = NUMERIC_LINE_CODE
    if isinstance(event.get("payload"), dict):
        event["payload"] = {
            **event["payload"],
            "lineCode": event["lineCode"],
            "processDomain": PROCESS_DOMAIN,
            "numericLineCode": NUMERIC_LINE_CODE,
        }
    return event
