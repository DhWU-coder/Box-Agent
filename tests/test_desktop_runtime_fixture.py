"""Deterministic desktop scenarios also run through real ACP stdio in CI."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import pytest

from tests.acp_host.probe import (
    AcpHostProbe, RpcError, collect_session_updates, message_text_from_updates,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["normal", "slow", "oversize", "timeout", "budget", "nested"])
async def test_desktop_fixture_reports_real_run_outcome(mode):
    workspace = Path(__file__).resolve().parents[1] / "workspace"
    workspace.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="desktop-fixture-", dir=workspace) as directory:
        root = Path(directory)
        probe = AcpHostProbe(
            command=[sys.executable, "-m", "tests.desktop_runtime_fixture"], cwd=root,
            env={"BOX_AGENT_DESKTOP_TEST_ROOT": str(root), "BOX_AGENT_HOME": str(root / "profile"),
                 "PYTHONUTF8": "1"}, timeout_s=20,
        )
        await probe.start()
        try:
            await probe.initialize()
            session = await probe.session_new(cwd=str(root / "profile/workspaces/test"))
            if mode in {"oversize", "timeout"}:
                with pytest.raises(RpcError) as raised:
                    await probe.session_prompt(session, f"fixture:{mode}")
                assert raised.value.code == -32603
            else:
                response = await probe.session_prompt(session, f"fixture:{mode}")
                assert response["stopReason"] == "end_turn"
            record = json.loads((root / "results.jsonl").read_text(encoding="utf-8").splitlines()[-1])
            assert record["scenario"] == mode
            if mode in {"oversize", "timeout"}:
                assert record["status"] == "failed"
                assert record["error"]["code"] == {
                    "oversize": "RUN_EVENT_TOO_LARGE", "timeout": "RUN_EVENT_CONSUMER_TIMEOUT",
                }[mode]
            else:
                assert record["status"] == "completed"
            if mode == "slow":
                text = message_text_from_updates(collect_session_updates(probe.drain_notifications()))
                assert text == "".join(f"piece-{index};" for index in range(40))
            if mode in {"budget", "nested"}:
                assert len(record["executions"]) == 3
            if mode == "nested":
                assert sorted(item["tool"] for item in record["executions"]) == [
                    "fixture_count", "fixture_nested", "fixture_nested",
                ]
        finally:
            await probe.stop()
