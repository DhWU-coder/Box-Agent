"""EOF notification must preserve framing and the platform stdio bridge."""

import asyncio

import pytest

from box_agent.acp import stdio_compat


@pytest.mark.asyncio
async def test_stdin_eof_notifies_after_buffered_frames_are_consumed():
    notifications = []
    reader = stdio_compat._StdioStreamReader(lambda: notifications.append("eof"))
    large_frame = b"x" * (128 * 1024) + b"\n"
    reader.feed_data(large_frame + b"\n" + b"last frame without newline")
    reader.feed_eof()
    assert await reader.readline() == large_frame
    assert await reader.readline() == b"\n"
    assert await reader.readline() == b"last frame without newline"
    assert not notifications
    assert await reader.readline() == b""
    assert await reader.readline() == b""
    assert notifications == ["eof"]


@pytest.mark.asyncio
async def test_cancelling_stdin_read_does_not_report_host_eof():
    closed = asyncio.Event()
    reader = stdio_compat._StdioStreamReader(closed.set)
    pending = asyncio.create_task(reader.readline())
    await asyncio.sleep(0)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert not closed.is_set()
    reader.feed_data(b"still connected\n")
    assert await reader.readline() == b"still connected\n"
    assert not closed.is_set()
    reader.feed_eof()
    assert await reader.readline() == b""
    assert closed.is_set()


@pytest.mark.asyncio
async def test_windows_stdio_feeder_uses_eof_notification(monkeypatch):
    closed = asyncio.Event()

    def feed(loop, reader):
        reader.feed_data(b"frame\n")
        reader.feed_eof()

    monkeypatch.setattr(stdio_compat, "_start_stdin_feeder", feed)
    monkeypatch.setattr(stdio_compat.platform, "system", lambda: "Windows")
    reader, writer = await stdio_compat.stdio_streams_largebuf(on_eof=closed.set)
    try:
        assert await reader.readline() == b"frame\n"
        assert not closed.is_set()
        assert await reader.readline() == b""
        assert closed.is_set()
    finally:
        writer.close()
