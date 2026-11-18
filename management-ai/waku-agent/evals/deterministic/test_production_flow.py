from langgraph.types import Command

from waku.ops.production_flow import create_material_loading_graph


def test_material_loading_requires_approval_then_proposes_event():
    graph = create_material_loading_graph()
    config = {"configurable": {"thread_id": "test-loading-1"}}
    initial = graph.invoke(
        {
            "work_order": "WO-1",
            "material_roll": "RSN001-1",
            "machine": "NPM-01",
            "channel": "1L",
            "feeder": "FD-01",
            "registered": True,
        },
        config,
    )
    assert initial["__interrupt__"]
    resumed = graph.invoke(Command(resume={"decision": "approve"}), config)
    assert resumed["result"] == "approved_pending_mes_write"
    assert resumed["proposed_event"]["machine"] == "NPM-01"


def test_material_loading_rejects_unregistered_roll():
    graph = create_material_loading_graph()
    config = {"configurable": {"thread_id": "test-loading-2"}}
    graph.invoke(
        {
            "work_order": "WO-1",
            "material_roll": "RSN-UNREGISTERED",
            "machine": "NPM-01",
            "channel": "1L",
            "feeder": "FD-01",
            "registered": False,
        },
        config,
    )
    rejected = graph.invoke(Command(resume={"decision": "approve"}), config)
    assert rejected["result"] == "rejected"
