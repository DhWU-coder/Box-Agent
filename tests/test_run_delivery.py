import asyncio
from types import SimpleNamespace

import pytest

from box_agent.agent_run import AgentRunHandle
from box_agent.events import ContentEvent, DoneEvent, StopReason
from box_agent.run_events import RunEventChannel


@pytest.mark.asyncio
async def test_channel_preserves_mixed_publisher_order():
    channel = RunEventChannel()
    await channel.publish("r", ContentEvent("one"))
    await channel.publish("r", ContentEvent("two"))
    channel.close()
    events = [await channel.get(), await channel.get()]
    assert [event.sequence for event in events] == [1, 2]
    assert [event.payload.content for event in events] == ["one", "two"]
    assert await channel.get() is channel.END


@pytest.mark.asyncio
@pytest.mark.parametrize("raises", [False, True])
async def test_run_without_terminal_reports_failure(raises):
    async def events():
        yield ContentEvent("partial")
        if raises:
            raise ValueError("broken")

    handle = AgentRunHandle.for_run(
        state=SimpleNamespace(), run_id="r", events_factory=events,
    )
    if raises:
        with pytest.raises(ValueError, match="broken"):
            _ = [event async for event in handle.events()]
    else:
        _ = [event async for event in handle.events()]
    result = await handle.result()
    assert result.status == "failed"
    assert result.error["type"] == ("ValueError" if raises else "MissingTerminalEvent")


def test_delivery_modules_do_not_import_adapters_or_models():
    import ast
    from pathlib import Path

    for name in ("run_events.py", "run_result.py"):
        tree = ast.parse((Path(__file__).parents[1] / "box_agent" / name).read_text())
        for node in ast.walk(tree):
            imports = ([node.module or ""] if isinstance(node, ast.ImportFrom)
                       else [item.name for item in node.names] if isinstance(node, ast.Import)
                       else [])
            assert not any(set(module.split(".")) & {"acp", "cli", "llm"} for module in imports)


@pytest.mark.parametrize("reason,kind", [
    ("end_turn", "normal"), ("max_steps", "budget_exhausted"),
    ("max_tokens", "budget_exhausted"), ("interrupted", "interrupted"),
    ("cancelled", "cancelled"), ("waiting_for_user", "waiting_for_user"),
    ("error", "failed"), ("vendor_reason", "unknown"),
])
def test_result_classifies_termination_without_changing_legacy_status(reason, kind):
    import json
    from box_agent.api import RunResult, RunStatus

    result = RunResult("r", RunStatus.COMPLETED, reason, "answer")
    assert result.status is RunStatus.COMPLETED
    assert result.stop_reason == reason
    assert result.termination_kind == kind
    assert json.loads(json.dumps(result.to_dict()))["termination_kind"] == kind
