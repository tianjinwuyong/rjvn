"""Canonical SMT line domain and MES local-information contract."""

PROCESS_DOMAIN = "SMT"
DOMAIN = "smt"
LINE_CODE = "L001"
NUMERIC_LINE_CODE = "001"
LOCAL_INFO_API_VERSION = "v1"
LOCAL_INFO_API_READ_ONLY = True
LOCAL_INFO_PORT_BASE = 12200
LOCAL_INFO_PORT_RANGE = (12201, 12207)


def resolve_line_code(station_code=""):
    code = str(station_code or "").strip().lower()
    if code and not code.startswith("smt_"):
        raise ValueError(f"Non-SMT station cannot run in {PROCESS_DOMAIN}: {station_code}")
    return LINE_CODE


def apply_line_domain(event, station_code=""):
    event = dict(event or {})
    event["lineCode"] = resolve_line_code(station_code or event.get("stationCode"))
    event["processDomain"] = PROCESS_DOMAIN
    event["domain"] = DOMAIN
    event["numericLineCode"] = NUMERIC_LINE_CODE
    if isinstance(event.get("payload"), dict):
        event["payload"] = {
            **event["payload"],
            "lineCode": event["lineCode"],
            "processDomain": PROCESS_DOMAIN,
            "domain": DOMAIN,
            "numericLineCode": NUMERIC_LINE_CODE,
        }
    return event
