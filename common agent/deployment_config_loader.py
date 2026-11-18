# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_deployment_config(path=None):
    path = Path(path or ROOT / "deployment_config.json")
    config = json.loads(path.read_text(encoding="utf-8"))
    profiles_path = path.parent / config.get("stationProfilesFile", "station_profiles.json")
    profiles = json.loads(profiles_path.read_text(encoding="utf-8")) if profiles_path.exists() else {"profiles": {}}
    config["stationProfiles"] = profiles.get("profiles", {})
    validate_deployment_config(config)
    return config


def validate_deployment_config(config):
    domains = set(config.get("supportedLineDomains", []))
    if not {"MANUAL_LINE", "AUTO_LINE"}.issubset(domains):
        raise ValueError("Both MANUAL_LINE and AUTO_LINE must be supported")
    if config.get("defaultLineDomain") not in domains:
        raise ValueError("Invalid defaultLineDomain")
    sqlite = config.get("sqlite") or {}
    if sqlite.get("enabled") is not True:
        raise ValueError("SQLite must be enabled for station-local history/outbox")
    if not sqlite.get("root") or "{stationCode}" not in str(sqlite.get("filePattern", "")):
        raise ValueError("SQLite root and stationCode filePattern are required")
    if str(sqlite.get("journalMode", "")).upper() not in {"WAL", "DELETE"}:
        raise ValueError("Unsupported SQLite journalMode")
    viewer = config.get("resourceViewer") or {}
    if viewer.get("enabled") is not True:
        raise ValueError("Local Resource Viewer must be enabled")
    if str(viewer.get("readMode", "")).lower() not in {"startup", "changed", "new", "partial"}:
        raise ValueError("Unsupported resource viewer readMode")
    if int(viewer.get("pollSeconds", 0)) < 1:
        raise ValueError("resource viewer pollSeconds must be positive")
    if not viewer.get("allowedFormats"):
        raise ValueError("resource viewer allowedFormats are required")
    kpi = config.get("kpiViewer") or {}
    if kpi.get("enabled") is not True:
        raise ValueError("KPI Viewer must be enabled")
    if int(kpi.get("refreshSeconds", 0)) < 1:
        raise ValueError("kpi refreshSeconds must be positive")
    if not kpi.get("metrics"):
        raise ValueError("KPI metrics are required")
    for metric in kpi["metrics"]:
        if not metric.get("key") or not metric.get("unit"):
            raise ValueError("KPI key and unit are required")
        if metric.get("direction") not in {"higher_is_better", "lower_is_better"}:
            raise ValueError("Invalid KPI direction")
    gates = config.get("qualityGates") or {}
    duplicate = gates.get("duplicateScan") or {}
    ng = gates.get("ngCheck") or {}
    if duplicate.get("enabled") is not True or int(duplicate.get("windowMs", 0)) < 0:
        raise ValueError("Duplicate scan gate is invalid")
    if duplicate.get("scope") not in {"STATION", "LINE", "GLOBAL"}:
        raise ValueError("Invalid duplicate scan scope")
    for key in ("requireSourceStation", "requireDefectCode", "requireRawEvidence", "preserveHistory", "mesAuthoritative", "blockUnknownSn"):
        if ng.get(key) is not True:
            raise ValueError("NG gate must enable " + key)
    scanner = config.get("scanner") or {}
    scanner_default = scanner.get("default") or {}
    if scanner_default.get("protocol") not in {"KEYBOARD_WEDGE", "USB_HID", "SERIAL", "TCP_CLIENT", "TCP_SERVER"}:
        raise ValueError("Invalid default scanner protocol")
    for station, scanner_profile in (scanner.get("byStation") or {}).items():
        protocol = scanner_profile.get("protocol", scanner_default.get("protocol"))
        port = scanner_profile.get("port", scanner_default.get("port"))
        if protocol not in {"KEYBOARD_WEDGE", "USB_HID", "SERIAL", "TCP_CLIENT", "TCP_SERVER"}:
            raise ValueError("Invalid scanner protocol for " + station)
        if protocol.startswith("TCP_") and not (1 <= int(port or 0) <= 65535):
            raise ValueError("TCP scanner port required for " + station)
    for station, profile in config.get("stationProfiles", {}).items():
        if profile.get("lineDomain") not in domains:
            raise ValueError("Invalid lineDomain for " + station)
        source = profile.get("dataSource") or {}
        if not source.get("type") or not source.get("formats"):
            raise ValueError("dataSource type/formats required for " + station)
        if not profile.get("mesDomain"):
            raise ValueError("mesDomain required for " + station)
        if not profile.get("motherboardLayout"):
            raise ValueError("motherboardLayout required for " + station)
    return True


def station_config(station_code, config=None):
    """Return the fully resolved runtime configuration for one station."""
    config = config or load_deployment_config()
    aliases = config.get("stationAliases", {})
    canonical = aliases.get(station_code, station_code)
    profile = dict(config.get("stationProfiles", {}).get(canonical) or {})
    if not profile:
        raise KeyError("No station profile: " + str(station_code))
    override = dict(config.get("stationOverrides", {}).get(station_code) or {})
    profile.update(override)
    profile["stationCode"] = canonical
    profile["requestedStationCode"] = station_code
    profile.setdefault("lineId", profile.get("lineDomain"))
    profile.setdefault("stationId", canonical.upper())
    profile["expectedHostIps"] = sorted(
        ip for ip, mapped in (config.get("ipToStation") or {}).items()
        if (config.get("stationAliases") or {}).get(mapped, mapped) == canonical
    )
    profile["sqlite"] = dict(config["sqlite"])
    profile["resourceViewer"] = dict(config["resourceViewer"])
    profile["kpiViewer"] = dict(config["kpiViewer"])
    profile["mes"] = dict(config.get("mesDomains", {}).get(profile.get("mesDomain", "MES"), {}))
    profile["qualityGates"] = dict(config["qualityGates"])
    scanner_config = dict((config.get("scanner") or {}).get("default") or {})
    scanner_config.update((config.get("scanner") or {}).get("byStation", {}).get(canonical) or {})
    profile["scanner"] = scanner_config
    return profile


__all__ = ["load_deployment_config", "validate_deployment_config", "station_config"]
