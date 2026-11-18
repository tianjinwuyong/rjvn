"""Safe, human-approved SMT material-loading workflow.

This is the first LangGraph boundary around the real production sequence.  It
does not write MES/WMS records yet: the final node returns a proposed loading
event, and the approval interrupt makes the boundary explicit before a future
MES adapter is connected.
"""

from __future__ import annotations

from typing import Any, Literal
from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class MaterialLoadingState(TypedDict, total=False):
    work_order: str
    material_roll: str
    machine: str
    channel: str
    feeder: str
    registered: bool
    expected: dict[str, str]
    verification: dict[str, Any]
    decision: dict[str, Any]
    proposed_event: dict[str, Any]
    result: str


def read_context(state: MaterialLoadingState) -> dict[str, Any]:
    """Normalize the scan payload; the MES adapter will populate registration later."""
    required = ("work_order", "material_roll", "machine", "channel", "feeder")
    missing = [key for key in required if not str(state.get(key, "")).strip()]
    return {"verification": {"missing": missing, "ready": not missing}}


def verify_scan(state: MaterialLoadingState) -> dict[str, Any]:
    """Verify registration and expected machine/channel/feeder without side effects."""
    expected = state.get("expected") or {}
    mismatches = {
        key: {"expected": expected[key], "actual": state.get(key, "")}
        for key in ("machine", "channel", "feeder")
        if expected.get(key) and expected[key] != state.get(key, "")
    }
    verification = dict(state.get("verification") or {})
    verification.update({"registered": bool(state.get("registered")), "mismatches": mismatches})
    verification["ok"] = bool(verification.get("ready")) and bool(state.get("registered")) and not mismatches
    return {"verification": verification}


def human_approval(state: MaterialLoadingState) -> Command[Literal["propose_loading", END]]:
    """Pause before any future MES/WMS write and require an explicit decision."""
    verification = state.get("verification") or {}
    decision = interrupt({
        "kind": "smt_material_loading_approval",
        "message": "Review the scanned machine, channel, feeder and material roll before loading.",
        "work_order": state.get("work_order", ""),
        "material_roll": state.get("material_roll", ""),
        "machine": state.get("machine", ""),
        "channel": state.get("channel", ""),
        "feeder": state.get("feeder", ""),
        "verification": verification,
        "allowed": ["approve", "reject"],
    })
    approved = isinstance(decision, dict) and decision.get("decision") == "approve"
    if approved and verification.get("ok"):
        return Command(update={"decision": decision}, goto="propose_loading")
    return Command(update={"decision": decision if isinstance(decision, dict) else {"decision": "reject"},
                           "result": "rejected"}, goto=END)


def propose_loading(state: MaterialLoadingState) -> dict[str, Any]:
    """Create a serializable event proposal; no production write occurs here."""
    event = {key: state.get(key, "") for key in ("work_order", "material_roll", "machine", "channel", "feeder")}
    event.update({"event": "SMT_MATERIAL_LOADING_APPROVED", "mode": "proposal_only"})
    return {"proposed_event": event, "result": "approved_pending_mes_write"}


def create_material_loading_graph():
    """Compile the workflow with an in-memory checkpointer for local testing."""
    builder = StateGraph(MaterialLoadingState)
    builder.add_node("read_context", read_context)
    builder.add_node("verify_scan", verify_scan)
    builder.add_node("human_approval", human_approval)
    builder.add_node("propose_loading", propose_loading)
    builder.add_edge(START, "read_context")
    builder.add_edge("read_context", "verify_scan")
    builder.add_edge("verify_scan", "human_approval")
    builder.add_edge("propose_loading", END)
    return builder.compile(checkpointer=InMemorySaver())


def start_loading(graph, state: MaterialLoadingState, thread_id: str):
    """Start a loading cycle on a retained graph/checkpointer."""
    return graph.invoke(state, {"configurable": {"thread_id": thread_id}})


_workflow = None


def get_loading_graph():
    """Return the process-local graph so an approval can be resumed by thread id."""
    global _workflow
    if _workflow is None:
        _workflow = create_material_loading_graph()
    return _workflow
