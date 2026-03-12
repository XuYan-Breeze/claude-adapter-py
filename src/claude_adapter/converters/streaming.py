"""Streaming converters 流式转换器

Convert OpenAI SSE streams to Anthropic SSE events
将 OpenAI SSE 流转换为 Anthropic SSE 事件
"""

import json
import secrets
import threading
from typing import Any, AsyncIterator, Optional

from .tools import generate_tool_use_id
from ..utils.token_usage import record_usage
from ..utils.error_log import record_error
from ..utils.logger import logger

_tool_id_counter = 0
_used_tool_ids: set = set()
_tool_id_lock = threading.Lock()


def _generate_unique_tool_id() -> str:
    global _tool_id_counter
    with _tool_id_lock:
        while True:
            _tool_id_counter += 1
            ts = format(_tool_id_counter, "x")
            rand = secrets.token_hex(5)
            candidate = f"call_{ts}_{rand}"
            if candidate not in _used_tool_ids:
                _used_tool_ids.add(candidate)
                if len(_used_tool_ids) > 10000:
                    to_remove = list(_used_tool_ids)[:5000]
                    for item in to_remove:
                        _used_tool_ids.discard(item)
                return candidate


class StreamState:
    __slots__ = (
        "message_id", "model", "response_model", "provider",
        "content_block_index", "current_tool_calls",
        "input_tokens", "output_tokens", "cached_input_tokens",
        "has_started", "text_content", "text_block_open",
        "finish_reason_received",
    )

    def __init__(self, request_id: str, model: str, provider: str = "") -> None:
        self.message_id = request_id
        self.model = model
        self.response_model = ""
        self.provider = provider
        self.content_block_index = 0
        self.current_tool_calls: dict[int, dict[str, str]] = {}
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_input_tokens = 0
        self.has_started = False
        self.text_content = ""
        self.text_block_open = False
        self.finish_reason_received = False


def _format_sse(data: dict[str, Any]) -> str:
    return f"event: {data['type']}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _send_message_start(state: StreamState) -> str:
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


def _send_content_block_start(
    index: int, block_type: str, text_or_name: str, tool_id: Optional[str] = None
) -> str:
    if block_type == "text":
        content_block: dict[str, Any] = {"type": "text", "text": ""}
    else:
        content_block = {
            "type": "tool_use",
            "id": tool_id or generate_tool_use_id(),
            "name": text_or_name,
            "input": {},
        }
    return _format_sse({
        "type": "content_block_start",
        "index": index,
        "content_block": content_block,
    })


def _send_text_delta(index: int, text: str) -> str:
    return _format_sse({
        "type": "content_block_delta",
        "index": index,
        "delta": {"type": "text_delta", "text": text},
    })


def _send_input_json_delta(index: int, partial_json: str) -> str:
    return _format_sse({
        "type": "content_block_delta",
        "index": index,
        "delta": {"type": "input_json_delta", "partial_json": partial_json},
    })


def _send_content_block_stop(index: int) -> str:
    return _format_sse({
        "type": "content_block_stop",
        "index": index,
    })


def _process_chunk(chunk: dict[str, Any], state: StreamState) -> list[str]:
    events: list[str] = []

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
        return events

    choice = choices[0]
    delta = choice.get("delta", {})

    if not state.has_started:
        events.append(_send_message_start(state))
        state.has_started = True

    if delta.get("content"):
        content_text = delta["content"]
        if state.text_content == "" and not state.text_block_open:
            events.append(
                _send_content_block_start(state.content_block_index, "text", "")
            )
            state.text_block_open = True

        state.text_content += content_text
        events.append(_send_text_delta(state.content_block_index, content_text))

    if delta.get("tool_calls"):
        for tc_delta in delta["tool_calls"]:
            tc_index = tc_delta["index"]

            if tc_index not in state.current_tool_calls:
                if state.text_block_open:
                    events.append(
                        _send_content_block_stop(state.content_block_index)
                    )
                    state.content_block_index += 1
                    state.text_block_open = False

                raw_id = tc_delta.get("id", "")
                with _tool_id_lock:
                    if raw_id and raw_id not in _used_tool_ids:
                        tool_id = raw_id
                        _used_tool_ids.add(tool_id)
                    else:
                        tool_id = _generate_unique_tool_id()

                name = ""
                if "function" in tc_delta and tc_delta["function"].get("name"):
                    name = tc_delta["function"]["name"]

                state.current_tool_calls[tc_index] = {
                    "id": tool_id,
                    "name": name,
                    "arguments": "",
                }

                block_index = state.content_block_index + tc_index
                events.append(
                    _send_content_block_start(
                        block_index, "tool_use", name, tool_id
                    )
                )

            current_call = state.current_tool_calls[tc_index]

            if "function" in tc_delta and tc_delta["function"].get("name"):
                current_call["name"] = tc_delta["function"]["name"]

            if "function" in tc_delta and tc_delta["function"].get("arguments"):
                args_delta = tc_delta["function"]["arguments"]
                current_call["arguments"] += args_delta
                block_index = state.content_block_index + tc_index
                events.append(_send_input_json_delta(block_index, args_delta))

    finish_reason = choice.get("finish_reason")
    if finish_reason:
        state.finish_reason_received = True

        if state.text_block_open:
            events.append(_send_content_block_stop(state.content_block_index))
            state.content_block_index += 1
            state.text_block_open = False

        for tc_idx in state.current_tool_calls:
            block_index = state.content_block_index + tc_idx
            events.append(_send_content_block_stop(block_index))

    return events


def _finish_stream(state: StreamState) -> list[str]:
    """Send final message_delta + message_stop.

    If finish_reason was already received from OpenAI, all content blocks
    were closed in _process_chunk — we only need message_delta + message_stop.

    If the stream was interrupted (no finish_reason), we close any still-open
    blocks here first, then send message_delta + message_stop with end_turn
    so Claude Code can continue instead of terminating the task.
    """
    events: list[str] = []

    if not state.finish_reason_received:
        if state.text_block_open:
            events.append(_send_content_block_stop(state.content_block_index))
            state.content_block_index += 1
            state.text_block_open = False

        for tc_idx in state.current_tool_calls:
            block_index = state.content_block_index + tc_idx
            events.append(_send_content_block_stop(block_index))

    has_tool_calls = len(state.current_tool_calls) > 0

    if state.finish_reason_received and has_tool_calls:
        stop_reason = "tool_use"
    elif state.finish_reason_received:
        stop_reason = "end_turn"
    else:
        stop_reason = "end_turn"

    record_usage(
        provider=state.provider,
        model_name=state.model,
        model=state.response_model or state.model,
        input_tokens=state.input_tokens,
        output_tokens=state.output_tokens,
        cached_input_tokens=state.cached_input_tokens or None,
        streaming=True,
    )

    events.append(_format_sse({
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason, "stop_sequence": None},
        "usage": {
            "output_tokens": state.output_tokens,
            "cache_read_input_tokens": state.cached_input_tokens,
        },
    }))
    events.append(_format_sse({"type": "message_stop"}))
    return events


async def convert_stream_to_anthropic(
    openai_stream: AsyncIterator[str],
    request_id: str,
    model: str,
    provider: str = "",
) -> AsyncIterator[str]:
    """Convert OpenAI SSE stream to Anthropic SSE events."""
    state = StreamState(request_id, model, provider)

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
                chunk_data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if "error" in chunk_data:
                error = chunk_data["error"]
                if isinstance(error, dict) and ("message" in error or "type" in error):
                    error_msg = error.get("message", "Unknown error")
                    if not state.has_started:
                        yield _send_message_start(state)
                        state.has_started = True
                    idx = state.content_block_index
                    yield _send_content_block_start(idx, "text", "")
                    yield _send_text_delta(idx, f"Error: {error_msg}")
                    yield _send_content_block_stop(idx)
                    yield _format_sse({
                        "type": "message_delta",
                        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                        "usage": {
                            "output_tokens": state.output_tokens,
                            "cache_read_input_tokens": state.cached_input_tokens,
                        },
                    })
                    yield _format_sse({"type": "message_stop"})
                    return

            for event in _process_chunk(chunk_data, state):
                yield event

    except Exception as e:
        record_error(e, state.message_id, state.provider, state.model, True)
        logger.warn(f"Stream exception: {str(e)[:200]}")
        if not state.has_started:
            yield _send_message_start(state)
            state.has_started = True
        if state.text_block_open:
            yield _send_content_block_stop(state.content_block_index)
        for tc_idx in state.current_tool_calls:
            yield _send_content_block_stop(state.content_block_index + tc_idx)
        yield _format_sse({
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {
                "output_tokens": state.output_tokens,
                "cache_read_input_tokens": state.cached_input_tokens,
            },
        })
        yield _format_sse({"type": "message_stop"})
        return

    if not state.has_started:
        yield _send_message_start(state)
        state.has_started = True

    for event in _finish_stream(state):
        yield event
