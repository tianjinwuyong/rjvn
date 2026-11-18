# -*- coding: utf-8 -*-
"""Shared duplicate-scan and NG evidence gates; MES remains authoritative."""
from __future__ import annotations


def check_duplicate(scan_record, *, mes_duplicate=False, config=None):
    config = config or {}
    gate = config.get("duplicateScan", {})
    if not gate.get("enabled", True):
        return {"accepted": True, "reason": "DUPLICATE_GATE_DISABLED"}
    if mes_duplicate or getattr(scan_record, "reason", "") == "DUPLICATE_SCAN":
        return {"accepted": not gate.get("blockOnDuplicate", True), "reason": "DUPLICATE_SCAN"}
    return {"accepted": True, "reason": "ACCEPTED"}


def check_ng_evidence(*, sn, source_station, defect_code, raw_evidence, config=None):
    config = config or {}
    gate = config.get("ngCheck", {})
    missing = []
    if gate.get("requireSourceStation", True) and not str(source_station or "").strip(): missing.append("SOURCE_STATION")
    if gate.get("requireDefectCode", True) and not str(defect_code or "").strip(): missing.append("DEFECT_CODE")
    if gate.get("requireRawEvidence", True) and not raw_evidence: missing.append("RAW_EVIDENCE")
    if gate.get("blockUnknownSn", True) and not str(sn or "").strip(): missing.append("SN")
    return {"accepted": not missing, "reason": "ACCEPTED" if not missing else "MISSING_NG_EVIDENCE", "missing": missing}


__all__ = ["check_duplicate", "check_ng_evidence"]
