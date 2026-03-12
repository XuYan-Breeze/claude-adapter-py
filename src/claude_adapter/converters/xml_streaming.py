"""XML Streaming converter XML 流式转换器

Convert OpenAI text stream to Anthropic SSE with XML tool call detection.
Uses buffered approach: accumulates complete tool calls before emitting.
将 OpenAI 文本流转换为 Anthropic SSE，带 XML 工具调用检测。
使用缓冲方式：在发出之前累积完整的工具调用。
"""

import json
import re
import secrets
from typing import Any, AsyncIterator

from .tools import generate_tool_use_id
from ..utils.token_usage import record_usage
from ..utils.error_log import record_error
from ..utils.logger import logger

THINK_BLOCK_PATTERN = re.compile(r"<think>[\s\S]*?</think>")
TOOL_CODE_PATTERN = re.compile(
    r'<tool_code\s+name\s*=\s*"([^"]+)"\s*>([\s\S]*?)</\s*tool_code\s*>', re.IGNORECASE
)
NESTED_TOOL_PATTERN = re.compile(r'<tool\s+name="[^"]*">\s*')
CLOSE_TOOL_PATTERN = re.compile(r"</tool>\s*")
LEADING_TOOLNAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*\n")


class _BufferedState:
    __slots__ = (
        "message_id", "model", "response_model", "provider",
        "content_block_index", "input_tokens", "output_tokens",
        "cached_input_tokens", "has_started", "buffer", "tool_calls_emitted",
    )

    def __init__(self, model: str, provider: str) -> None:
        self.message_id = f"msg_{secrets.token_urlsafe(18)[:24]}"
        self.model = model
        self.response_model = ""
        self.provider = provider
        self.content_block_index = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_input_tokens = 0
        self.has_started = False
        self.buffer = ""
        self.tool_calls_emitted = 0


def _format_sse(data: dict[str, Any]) -> str:
    return f"event: {data['type']}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _clean_tool_args(args: str) -> str:
    cleaned = NESTED_TOOL_PATTERN.sub("", args)
    cleaned = CLOSE_TOOL_PATTERN.sub("", cleaned)
    cleaned = LEADING_TOOLNAME_PATTERN.sub("", cleaned)
    return cleaned.strip()


def _emit_text_block(text: str, state: _BufferedState) -> list[str]:
    idx = state.content_block_index
    events = [
        _format_sse({
            "type": "content_block_start",
            "index": idx,
            "content_block": {"type": "text", "text": ""},
        }),
        _format_sse({
            "type": "content_block_delta",
            "index": idx,
            "delta": {"type": "text_delta", "text": text},
        }),
        _format_sse({
            "type": "content_block_stop",
            "index": idx,
        }),
    ]
    state.content_block_index += 1
    return events


def _emit_tool_use_block(tool_name: str, args: str, state: _BufferedState) -> list[str]:
    tool_id = generate_tool_use_id()
    idx = state.content_block_index
    events = [
        _format_sse({
            "type": "content_block_start",
            "index": idx,
            "content_block": {
                "type": "tool_use",
                "id": tool_id,
                "name": tool_name,
                "input": {},
            },
        }),
        _format_sse({
            "type": "content_block_delta",
            "index": idx,
            "delta": {"type": "input_json_delta", "partial_json": args},
        }),
        _format_sse({
            "type": "content_block_stop",
            "index": idx,
        }),
    ]
    state.content_block_index += 1
    state.tool_calls_emitted += 1
    return events


def _process_buffer(state: _BufferedState) -> list[str]:
    """Extract complete tool calls from buffer, emitting text and tool_use blocks."""
    events: list[str] = []
    while True:
        clean_buf = THINK_BLOCK_PATTERN.sub("", state.buffer)
        m = TOOL_CODE_PATTERN.search(clean_buf)
        if not m:
            break

        tool_name = m.group(1)
        raw_args = m.group(2)
        match_start = m.start()

        text_before = clean_buf[:match_start].strip()
        if text_before:
            events.extend(_emit_text_block(text_before, state))

        cleaned_args = _clean_tool_args(raw_args)
        events.extend(_emit_tool_use_block(tool_name, cleaned_args, state))

        end_tag = "</tool_code>"
        end_pos = state.buffer.find(end_tag)
        if end_pos >= 0:
            state.buffer = state.buffer[end_pos + len(end_tag):]
        else:
            state.buffer = ""
    return events


def _flush_remaining(state: _BufferedState) -> list[str]:
    clean_buf = THINK_BLOCK_PATTERN.sub("", state.buffer).strip()
    if clean_buf:
        return _emit_text_block(clean_buf, state)
    return []


def _message_start_event(state: _BufferedState) -> str:
    return _format_sse({
        "type": "message_start",
        "message": {
            "id": state.message_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": state.model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {
                "input_tokens": state.input_tokens,
                "output_tokens": state.output_tokens,
                "cache_read_input_tokens": state.cached_input_tokens,
            },
        },
    })


def _finish_events(state: _BufferedState) -> list[str]:
    stop_reason = "tool_use" if state.tool_calls_emitted > 0 else "end_turn"

    record_usage(
        provider=state.provider,
        model_name=state.model,
        model=state.response_model or state.model,
        input_tokens=state.input_tokens,
        output_tokens=state.output_tokens,
        cached_input_tokens=state.cached_input_tokens or None,
        streaming=True,
    )

    return [
        _format_sse({
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            "usage": {
                "output_tokens": state.output_tokens,
                "cache_read_input_tokens": state.cached_input_tokens,
            },
        }),
        _format_sse({"type": "message_stop"}),
    ]


def _graceful_end_events(state: _BufferedState) -> list[str]:
    """Gracefully end stream so Claude Code can continue."""
    return [
        _format_sse({
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {
                "output_tokens": state.output_tokens,
                "cache_read_input_tokens": state.cached_input_tokens,
            },
        }),
        _format_sse({"type": "message_stop"}),
    ]


async def convert_xml_stream_to_anthropic(
    openai_stream: AsyncIterator[str],
    request_id: str,
    model: str,
    provider: str = "",
) -> AsyncIterator[str]:
    """Convert OpenAI SSE stream (text containing XML tool calls) to Anthropic SSE events.

    Unlike the native streaming converter, this buffers text and detects
    <tool_code name="...">...</tool_code> patterns, converting them to
    Anthropic tool_use content blocks.
    """
    state = _BufferedState(model, provider)
    state.message_id = request_id

    try:
        async for line in openai_stream:
            stripped = line.strip()
            if not stripped or stripped.startswith(":"):
                continue

            if not stripped.startswith("data: "):
                continue

            data_str = stripped[6:].strip()
            if data_str == "[DONE]":
                break

            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if "error" in chunk:
                error = chunk["error"]
                if isinstance(error, dict) and ("message" in error or "type" in error):
                    error_msg = error.get("message", "Unknown error")
                    if not state.has_started:
                        yield _message_start_event(state)
                        state.has_started = True
                    for ev in _emit_text_block(f"Error: {error_msg}", state):
                        yield ev
                    for ev in _graceful_end_events(state):
                        yield ev
                    return

            if "usage" in chunk and chunk["usage"]:
                usage = chunk["usage"]
                state.input_tokens = usage.get("prompt_tokens", 0)
                state.output_tokens = usage.get("completion_tokens", 0)
                details = usage.get("prompt_tokens_details") or {}
                state.cached_input_tokens = details.get("cached_tokens", 0)

            if chunk.get("model") and not state.response_model:
                state.response_model = chunk["model"]

            choices = chunk.get("choices")
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta", {})
            text_delta = delta.get("content") or ""
            if not text_delta:
                continue

            if not state.has_started:
                yield _message_start_event(state)
                state.has_started = True

            state.buffer += text_delta

            for ev in _process_buffer(state):
                yield ev

        # Flush remaining text
        if not state.has_started:
            yield _message_start_event(state)
            state.has_started = True

        for ev in _flush_remaining(state):
            yield ev

        for ev in _finish_events(state):
            yield ev

    except Exception as e:
        record_error(e, state.message_id, state.provider, state.model, True)
        logger.warn(f"XML stream exception: {str(e)[:200]}")
        if not state.has_started:
            yield _message_start_event(state)
            state.has_started = True
        for ev in _flush_remaining(state):
            yield ev
        for ev in _graceful_end_events(state):
            yield ev
