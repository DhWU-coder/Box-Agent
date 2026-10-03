"""Payload ownership and SDK dispatch/reply contracts for long-lived ACP."""

import asyncio
import gc
import json
import weakref

import pytest
from acp.connection import Connection
from acp.exceptions import RequestError
from acp.task.dispatcher import DefaultMessageDispatcher
from acp.task.queue import InMemoryMessageQueue
from acp.task.supervisor import TaskSupervisor

from box_agent.acp.request_state import RequestStateStore


class Payload:
    def __init__(self):
        self.content = bytearray(256 * 1024)


@pytest.mark.parametrize("outcome", ["success", "error"])
def test_finished_request_does_not_keep_body_result_or_error_locals(outcome):
    store = RequestStateStore()

    def finish():
        body, response = Payload(), Payload()
        refs = weakref.ref(body), weakref.ref(response)
        record = store.begin_incoming("session/prompt", {"body": body})
        if outcome == "success":
            store.complete_incoming(record, {"response": response})
        else:
            try:
                raise RuntimeError("request failed with locals in its traceback")
            except RuntimeError as error:
                store.fail_incoming(record, error)
        return record, refs

    # Even if a diagnostic caller holds the record, it must not retain payloads.
    record, refs = finish()
    gc.collect()
    assert all(ref() is None for ref in refs)
    assert record.status == ("completed" if outcome == "success" else "failed")


@pytest.mark.asyncio
@pytest.mark.parametrize("started", [False, True])
async def test_cancelled_sdk_request_releases_body_without_completion_callback(started):
    store = RequestStateStore()
    supervisor = TaskSupervisor(source="request-state-test")
    entered = asyncio.Event()

    async def request(message):
        entered.set()
        await asyncio.Event().wait()

    async def notification(message):
        pass

    dispatcher = DefaultMessageDispatcher(
        queue=InMemoryMessageQueue(), supervisor=supervisor, store=store,
        request_runner=request, notification_runner=notification,
    )
    body = Payload()
    ref = weakref.ref(body)
    try:
        await dispatcher._dispatch_request({"method": "session/new", "params": body})
        del body
        if started:
            await asyncio.wait_for(entered.wait(), 2)
    finally:
        # Call inline so the False case cancels before the child ever starts.
        await supervisor.shutdown()
    assert entered.is_set() is started
    await asyncio.sleep(0)
    gc.collect()
    assert ref() is None


@pytest.mark.asyncio
async def test_host_reply_futures_survive_unrelated_incoming_requests():
    store = RequestStateStore()
    permission_a = store.register_outgoing(10, "session/request_permission")
    permission_b = store.register_outgoing(11, "session/request_permission")
    host_read = store.register_outgoing(12, "fs/read_text_file")
    for _ in range(32):
        store.complete_incoming(store.begin_incoming("session/prompt", {}), {"stopReason": "end_turn"})
    assert not permission_a.done() and not permission_b.done() and not host_read.done()
    store.resolve_outgoing(11, {"outcome": "selected", "session": "b"})
    assert await permission_b == {"outcome": "selected", "session": "b"}
    assert not permission_a.done()
    store.reject_outgoing(12, RequestError(-32000, "host read failed"))
    with pytest.raises(RequestError, match="host read failed"):
        await host_read
    store.reject_all_outgoing(ConnectionError("host disconnected"))
    with pytest.raises(ConnectionError, match="host disconnected"):
        await permission_a


@pytest.mark.asyncio
async def test_sdk_delivers_response_and_error_before_releasing_request_payload():
    writes = asyncio.Queue()

    class Writer:
        def write(self, data):
            writes.put_nowait(json.loads(data))

        async def drain(self):
            await asyncio.sleep(0)

    async def handle(method, params, is_notification):
        if method == "_fail":
            raise RequestError(-32010, "SESSION_BUSY", {"sessionId": params["sessionId"]})
        return {"sessionId": params["sessionId"], "content": params["content"]}

    reader = asyncio.StreamReader()
    store = RequestStateStore()
    connection = Connection(handle, Writer(), reader, state_store=store)
    try:
        for request_id, method in enumerate(["_echo", "_fail", "_echo"]):
            content = "response-body-" * 100
            reader.feed_data((json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method,
                "params": {"sessionId": "a" if request_id % 2 == 0 else "b", "content": content}}) + "\n").encode())
            response = await asyncio.wait_for(writes.get(), 2)
            assert response["id"] == request_id
            if method == "_fail":
                assert response["error"] == {"code": -32010, "message": "SESSION_BUSY", "data": {"sessionId": "b"}}
            else:
                assert response["result"] == {"sessionId": "a", "content": content}
    finally:
        reader.feed_eof()
        await asyncio.wait_for(connection.close(), 2)
