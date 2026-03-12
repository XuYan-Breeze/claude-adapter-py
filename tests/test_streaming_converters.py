"""Streaming converter tests 流式转换器测试

Focus on graceful termination behavior for error/interruption cases.
重点验证错误/中断时的优雅收敛行为。
"""

import pytest

from claude_adapter.converters.streaming import convert_stream_to_anthropic
from claude_adapter.converters.xml_streaming import convert_xml_stream_to_anthropic


async def _collect(async_iter):
    return [item async for item in async_iter]


@pytest.mark.asyncio
async def test_xml_stream_error_chunk_graceful_end(monkeypatch):
    monkeypatch.setattr("claude_adapter.converters.xml_streaming.record_usage", lambda **_: None)
    monkeypatch.setattr("claude_adapter.converters.xml_streaming.record_error", lambda *_, **__: None)

    async def source():
        yield 'data: {"error":{"message":"upstream failed","type":"api_error"}}\n\n'

    events = await _collect(
        convert_xml_stream_to_anthropic(source(), "msg_test_xml_err", "claude-sonnet")
    )
    joined = "".join(events)

    assert "event: message_start" in joined
    assert "Error: upstream failed" in joined
    assert '"stop_reason": "end_turn"' in joined
    assert "event: message_stop" in joined
    assert "event: error" not in joined


@pytest.mark.asyncio
async def test_xml_stream_exception_graceful_end(monkeypatch):
    monkeypatch.setattr("claude_adapter.converters.xml_streaming.record_usage", lambda **_: None)
    monkeypatch.setattr("claude_adapter.converters.xml_streaming.record_error", lambda *_, **__: None)

    async def source():
        # Leave unfinished text in buffer, then raise
        yield 'data: {"choices":[{"delta":{"content":"partial text"}}]}\n\n'
        raise RuntimeError("network closed")

    events = await _collect(
        convert_xml_stream_to_anthropic(source(), "msg_test_xml_exc", "claude-sonnet")
    )
    joined = "".join(events)

    assert "event: message_start" in joined
    assert "partial text" in joined
    assert '"stop_reason": "end_turn"' in joined
    assert "event: message_stop" in joined
    assert "event: error" not in joined


@pytest.mark.asyncio
async def test_native_stream_error_chunk_graceful_end(monkeypatch):
    monkeypatch.setattr("claude_adapter.converters.streaming.record_usage", lambda **_: None)
    monkeypatch.setattr("claude_adapter.converters.streaming.record_error", lambda *_, **__: None)

    async def source():
        yield 'data: {"error":{"message":"bad request","type":"invalid_request_error"}}\n\n'

    events = await _collect(
        convert_stream_to_anthropic(source(), "msg_test_native_err", "claude-sonnet")
    )
    joined = "".join(events)

    assert "event: message_start" in joined
    assert "Error: bad request" in joined
    assert '"stop_reason": "end_turn"' in joined
    assert "event: message_stop" in joined
    assert "event: error" not in joined
