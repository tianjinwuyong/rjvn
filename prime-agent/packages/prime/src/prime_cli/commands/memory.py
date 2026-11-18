"""Commands for optional external agent memory backends."""

from __future__ import annotations

import json

import typer

from ..api.brainoutside import BrainOutsideClient, BrainOutsideError
from ..utils import PlainTyper, get_console

app = PlainTyper(help="Connect Prime to external agent memory.")
brainoutside_app = PlainTyper(help="Use a BrainOutside knowledge server (read-only).")
app.add_typer(brainoutside_app, name="brainoutside")
console = get_console()


def _client() -> BrainOutsideClient:
    return BrainOutsideClient()


@brainoutside_app.command("status")
def status() -> None:
    """Check that BrainOutside is reachable and authenticated."""
    try:
        console.print(json.dumps(_client().ping(), indent=2))
    except BrainOutsideError as exc:
        raise typer.BadParameter(str(exc)) from exc


@brainoutside_app.command("context")
def context(
    task: str = typer.Argument(..., help="Task to assemble context for."),
    lens: str = typer.Option("", "--lens", help="Optional BrainOutside lens."),
) -> None:
    """Retrieve an approved context pack for a task."""
    try:
        result = _client().assemble_context(task, lens=lens)
    except BrainOutsideError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(result.get("context_pack", ""))


@brainoutside_app.command("notes")
def notes(
    kind: str = typer.Option("", "--kind"),
    topic: str = typer.Option("", "--topic"),
    project: str = typer.Option("", "--project"),
    status_filter: str = typer.Option("current", "--status"),
    output: str = typer.Option("json", "--output", "-o"),
) -> None:
    """List approved notes visible to the configured BrainOutside key."""
    try:
        result = _client().list_notes(
            kind=kind, topic=topic, project=project, status=status_filter
        )
    except BrainOutsideError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if output == "json":
        console.print(json.dumps(result, indent=2))
        return
    if output != "text":
        raise typer.BadParameter("--output must be json or text")
    for note in result.get("notes", []):
        console.print(f"{note.get('entity_id', '')}\t{note.get('title', '')}")
