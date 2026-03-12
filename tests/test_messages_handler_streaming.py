"""Messages handler streaming tests 消息处理器流式测试"""

from __future__ import annotations

import pytest

from claude_adapter.handlers.messages import handle_messages_request
from claude_adapter.models.config import AdapterConfig, ModelConfig


class _FakeRequest:
    def __init__(self, body: dict):
        self._body = body

    async def json(self):
        return self._body


class _RaisingCompletions:
    def __init__(self, error: Exception):
        self._error = error

    async def create(self, **kwargs):
        raise self._error


class _RaisingClient:
    def __init__(self, error: Exception):
        class _Chat:
            def __init__(self, err: Exception):
                self.completions = _RaisingCompletions(err)

        self.chat = _Chat(error)


def _make_config() -> AdapterConfig:
    return AdapterConfig(
        provider="nvidia",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key="test",
        models=ModelConfig(
            opus="openai/gpt-oss-120b",
            sonnet="openai/gpt-oss-120b",
            haiku="openai/gpt-oss-120b",
        ),
        tool_format="native",
    )


def _make_stream_request_body() -> dict:
    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 256,
        "stream": True,
        "messages": [{"role": "user", "content": "hello"}],
    }


async def _collect_streaming_response(response) -> str:
    chunks: list[str] = []
    async for item in response.body_iterator:
        if isinstance(item, bytes):
            chunks.append(item.decode("utf-8", errors="replace"))
        else:
            chunks.append(item)
    return "".join(chunks)


@pytest.mark.asyncio
async def test_stream_start_runtime_error_returns_graceful_sse(monkeypatch):
    monkeypatch.setattr(
        "claude_adapter.handlers.messages._get_openai_client",
        lambda _cfg: _RaisingClient(RuntimeError("peer closed connection")),
    )
    monkeypatch.setattr("claude_adapter.handlers.messages.record_error", lambda *_, **__: None)

    response = await handle_messages_request(_FakeRequest(_make_stream_request_body()), _make_config())
    payload = await _collect_streaming_response(response)

    assert response.media_type == "text/event-stream"
    assert "event: message_start" in payload
    assert '"stop_reason": "end_turn"' in payload
    assert "event: message_stop" in payload


@pytest.mark.asyncio
async def test_stream_start_401_returns_http_error(monkeypatch):
    class _AuthError(Exception):
        status_code = 401

    monkeypatch.setattr(
        "claude_adapter.handlers.messages._get_openai_client",
        lambda _cfg: _RaisingClient(_AuthError("unauthorized")),
    )
    monkeypatch.setattr("claude_adapter.handlers.messages.record_error", lambda *_, **__: None)

    response = await handle_messages_request(_FakeRequest(_make_stream_request_body()), _make_config())

    assert response.status_code == 401
