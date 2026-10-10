"""ACP cancellation interrupts provider waits without restarting shared runtime."""

import asyncio
from types import SimpleNamespace

import pytest

from box_agent.acp import BoxACPAgent
from box_agent.config import AgentConfig, Config, LLMConfig, ToolsConfig
from box_agent.schema import StreamEvent


@pytest.mark.asyncio
@pytest.mark.parametrize("partial_output", [False, True])
async def test_acp_cancel_wakes_stalled_model_and_keeps_sessions_usable(tmp_path, partial_output):
    started, closed = asyncio.Event(), asyncio.Event()
    other_started, release_other = asyncio.Event(), asyncio.Event()

    class Model:
        calls = 0

        async def generate_stream(self, messages, tools=None, **kwargs):
            self.calls += 1
            if self.calls == 1:
                try:
                    if partial_output:
                        yield StreamEvent(type="text", delta="partial")
                    started.set()
                    await asyncio.Event().wait()
                finally:
                    closed.set()
            elif self.calls == 2:
                other_started.set()
                await release_other.wait()
            yield StreamEvent(type="text", delta="done")
            yield StreamEvent(type="finish", finish_reason="stop")

    class Conn:
        async def sessionUpdate(self, payload):
            pass

    config = Config(
        llm=LLMConfig(api_key="test-key"),
        agent=AgentConfig(max_steps=1, workspace_dir=str(tmp_path)),
        tools=ToolsConfig(enable_sub_agent=False, enable_mcp=False),
    )
    agent = BoxACPAgent(Conn(), config, Model(), [], "system")
    first = await agent.newSession(SimpleNamespace(cwd=str(tmp_path), field_meta={}))
    second = await agent.newSession(SimpleNamespace(cwd=str(tmp_path), field_meta={}))

    async def prompt(session_id):
        return await agent.prompt(SimpleNamespace(sessionId=session_id, prompt=[{"text": "hello"}]))

    pending = asyncio.create_task(prompt(first.sessionId))
    other_pending = None
    try:
        await asyncio.wait_for(started.wait(), 2)
        other_pending = asyncio.create_task(prompt(second.sessionId))
        await asyncio.wait_for(other_started.wait(), 2)
        await agent.cancel(SimpleNamespace(sessionId=first.sessionId))
        response = await asyncio.wait_for(asyncio.shield(pending), 1)
        assert response.stopReason == "cancelled"
        assert closed.is_set()
        state = agent._sessions[first.sessionId]
        assert not state._prompt_in_progress
        assert not state.run_handle.is_active
        assert not other_pending.done(), "cancelling one run must not interrupt another"
        release_other.set()
        other = await asyncio.wait_for(other_pending, 2)
        assert other.stopReason == "end_turn"
        # No runtime restart or replacement session is needed to send again.
        resumed = await asyncio.wait_for(prompt(first.sessionId), 2)
        assert resumed.stopReason == "end_turn"
    finally:
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        if other_pending is not None:
            other_pending.cancel()
            await asyncio.gather(other_pending, return_exceptions=True)
        await agent.aclose()
