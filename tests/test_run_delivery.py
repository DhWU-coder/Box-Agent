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
