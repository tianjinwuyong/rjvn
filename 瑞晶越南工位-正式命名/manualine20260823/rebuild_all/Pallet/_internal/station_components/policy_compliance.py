"""MES policy-compliance facts for Station Agents.

This module is deliberately transport-neutral: callers send the returned
append-only report through the approved MES connection/outbox component.
"""
from __future__ import annotations

from typing import Any, Dict, List


def _required_components(policy: Dict[str, Any]) -> List[str]:
    values = policy.get("requiredComponents") or []
    return [str(value).strip() for value in values if str(value).strip()]


def build_compliance_report(
    policy: Dict[str, Any], observed: Dict[str, Any], observed_at_ms: int
) -> Dict[str, Any]:
    """Compare a published MES policy with local facts and create a report.

    The report contains no decision authority. A non-compliant result is a
    fact for MES supervision; it must not be converted into local routing or
    release behavior by an Agent.
    """
    if observed_at_ms <= 0:
        raise ValueError("observed_at_ms must be positive")

    violations: List[str] = []
    for field, code in (
        ("domain", "DOMAIN_MISMATCH"),
        ("lineCode", "LINE_MISMATCH"),
        ("stationCode", "STATION_MISMATCH"),
        ("routeRevision", "ROUTE_REVISION_MISMATCH"),
    ):
        expected = policy.get(field)
        if expected is not None and str(observed.get(field, "")) != str(expected):
            violations.append(code)

    if policy.get("policyVersion") is not None and observed.get("policyVersion") != policy.get("policyVersion"):
        violations.append("POLICY_VERSION_MISMATCH")

    components = observed.get("componentVersions") or {}
    for component in _required_components(policy):
        if component not in components:
            violations.append(f"MISSING_COMPONENT:{component}")

    if not observed.get("mesOnline", False):
        violations.append("MES_OFFLINE")

    state = "OFFLINE" if not observed.get("mesOnline", False) else ("COMPLIANT" if not violations else "NON_COMPLIANT")
    station = str(observed.get("stationCode") or policy.get("stationCode") or "").strip()
    policy_version = str(observed.get("policyVersion") or policy.get("policyVersion") or "unknown")
    return {
        "eventType": "STATION_POLICY_COMPLIANCE",
        "eventId": f"compliance:{station}:{policy_version}:{observed_at_ms}",
        "observedAtMs": observed_at_ms,
        "complianceState": state,
        "compliant": state == "COMPLIANT",
        "violations": violations,
        "domain": observed.get("domain") or policy.get("domain"),
        "lineCode": observed.get("lineCode") or policy.get("lineCode"),
        "stationCode": station,
        "hostIp": observed.get("hostIp"),
        "agentVersion": observed.get("agentVersion"),
        "componentVersions": dict(components),
        "policyVersion": observed.get("policyVersion"),
        "routeRevision": observed.get("routeRevision"),
    }
