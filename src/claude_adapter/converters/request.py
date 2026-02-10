"""Request converter 请求转换器

Convert Anthropic Messages API requests to OpenAI Chat Completions format
将 Anthropic Messages API 请求转换为 OpenAI Chat Completions 格式
"""

import json
from typing import Any, Literal, Optional

from ..models.anthropic import (
    AnthropicMessageRequest,
    AnthropicMessage,
    AnthropicContentBlock,
    AnthropicTextBlock,
    AnthropicToolUseBlock,
    AnthropicToolResultBlock,
    AnthropicSystemContent,
)
from ..models.config import AdapterConfig
from .tools import convert_tools_to_openai, convert_tool_choice_to_openai
from .xml_prompt import generate_xml_tool_instructions
from ..utils.update import get_cached_update_info
from ..utils.metadata import CURRENT_VERSION
from ..providers import get_provider_preset
from ..utils.logger import logger

CLAUDE_CODE_IDENTIFIER = "You are Claude Code, Anthropic's official CLI for Claude."
CONTEXT_RESERVE_TOKENS = 256


def _estimate_tokens(text: str) -> int:
    """Rough token count estimate (conservative: ~2.5 chars per token)."""
    if not text:
        return 0
    return max(1, (len(text) * 2 + 1) // 5)


def _estimate_message_tokens(msg: dict[str, Any]) -> int:
    """Estimate token count for one OpenAI-format message."""
    content = msg.get("content")
    if content is None:
        return 0
    if isinstance(content, str):
        return _estimate_tokens(content)
    if isinstance(content, list):
        total = 0
        for part in content:
            if isinstance(part, dict) and "text" in part and isinstance(part["text"], str):
                total += _estimate_tokens(part["text"])
            else:
                total += 2
        return total
    return _estimate_tokens(str(content))


def _truncate_text_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text so estimated token count <= max_tokens (conservative 2 chars/token)."""
    if max_tokens <= 0:
        return ""
    max_chars = max_tokens * 2
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[... truncated ...]"


def _truncate_messages_to_fit(
    messages: list[dict[str, Any]],
    max_prompt_tokens: int,
) -> list[dict[str, Any]]:
    """Drop oldest non-system messages and truncate system if needed so prompt fits."""
    if max_prompt_tokens <= 0:
        return messages

    total = sum(_estimate_message_tokens(m) for m in messages)
    if total <= max_prompt_tokens:
        return messages

    system_msgs: list[dict[str, Any]] = []
    rest: list[dict[str, Any]] = []
    for m in messages:
        if m.get("role") == "system":
            system_msgs.append(m)
        else:
            rest.append(m)

    system_tokens = sum(_estimate_message_tokens(m) for m in system_msgs)
    budget_rest = max(0, max_prompt_tokens - system_tokens)

    if budget_rest <= 0 and system_msgs:
        system_budget = max(256, max_prompt_tokens - 512)
        combined_system: list[dict[str, Any]] = []
        running = 0
        for m in system_msgs:
            t = _estimate_message_tokens(m)
            content = m.get("content")
            if isinstance(content, str):
                if running + t <= system_budget:
                    combined_system.append(m)
                    running += t
                else:
                    allowed = max(0, system_budget - running)
                    truncated = _truncate_text_to_tokens(content, allowed)
                    combined_system.append({**m, "content": truncated})
                    running += _estimate_message_tokens(truncated)
                    break
            else:
                combined_system.append(m)
                running += t
        budget_after_system = max(0, max_prompt_tokens - running)
        kept_rest = []
        r = 0
        for m in reversed(rest):
            t = _estimate_message_tokens(m)
            if r + t <= budget_after_system:
                kept_rest.append(m)
                r += t
            else:
                break
        kept_rest.reverse()
        return combined_system + kept_rest

    if budget_rest <= 0:
        return system_msgs if system_msgs else messages[:1]

    kept = []
    running = 0
    for m in reversed(rest):
        t = _estimate_message_tokens(m)
        if running + t <= budget_rest:
            kept.append(m)
            running += t
        else:
            break
    kept.reverse()
    return system_msgs + kept


def _modify_system_prompt_for_adapter(system_content: str) -> str:
    """Replace Claude Code identifier with adapter branding."""
    if CLAUDE_CODE_IDENTIFIER not in system_content:
        return system_content
    update_info = get_cached_update_info()
    replacement = (
        f"You are Claude Code, running on Claude Adapter Python V{CURRENT_VERSION}. "
        "When introducing yourself, mention Claude Adapter."
    )
    if update_info and update_info.has_update:
        replacement += (
            f" A new version is available ({update_info.current} → {update_info.latest}). "
            "Suggest 'pip install --upgrade claude-adapter-py' to update."
        )
    return system_content.replace(CLAUDE_CODE_IDENTIFIER, replacement)


class _IdDeduplicationContext:
    def __init__(self) -> None:
        self.seen_ids: set[str] = set()
        self.id_mappings: dict[str, list[str]] = {}
        self.result_index: dict[str, int] = {}


def _deduplicate_tool_id(tool_id: str, ctx: _IdDeduplicationContext) -> str:
    """Deduplicate tool ID for OpenAI (unique per request)."""
    if tool_id not in ctx.seen_ids:
        ctx.seen_ids.add(tool_id)
        ctx.id_mappings[tool_id] = [tool_id]
        ctx.result_index[tool_id] = 0
    mapping = ctx.id_mappings[tool_id]
    idx = ctx.result_index[tool_id] % len(mapping)
    ctx.result_index[tool_id] += 1
    return mapping[idx]


def _convert_message(
    msg: AnthropicMessage,
    ctx: _IdDeduplicationContext,
    tool_format: Literal["native", "xml"],
) -> list[dict[str, Any]]:
    """Convert one Anthropic message to one or more OpenAI-format message dicts."""
    out: list[dict[str, Any]] = []
    content = msg.content

    if msg.role == "user":
        if isinstance(content, str):
            out.append({"role": "user", "content": content})
        else:
            text_parts: list[str] = []
            tool_results: list[tuple[str, str]] = []
            for block in content:
                if isinstance(block, AnthropicTextBlock):
                    text_parts.append(block.text)
                elif isinstance(block, AnthropicToolResultBlock):
                    c = block.content
                    tool_results.append((block.tool_use_id, c if isinstance(c, str) else json.dumps(c)))
            if text_parts:
                out.append({"role": "user", "content": "\n".join(text_parts)})
            for tid, c in tool_results:
                out.append({"role": "tool", "content": c, "tool_call_id": _deduplicate_tool_id(tid, ctx)})

    elif msg.role == "assistant":
        if isinstance(content, str):
            out.append({"role": "assistant", "content": content or ""})
        else:
            text_parts = []
            tool_calls: list[dict[str, Any]] = []
            for block in content:
                if isinstance(block, AnthropicTextBlock):
                    text_parts.append(block.text)
                elif isinstance(block, AnthropicToolUseBlock):
                    oid = _deduplicate_tool_id(block.id, ctx)
                    tool_calls.append({
                        "id": oid,
                        "type": "function",
                        "function": {"name": block.name, "arguments": json.dumps(block.input)},
                    })
            content_str = "\n".join(text_parts) if text_parts else ""
            if tool_calls:
                out.append({
                    "role": "assistant",
                    "content": content_str or None,
                    "tool_calls": tool_calls,
                })
            else:
                out.append({"role": "assistant", "content": content_str or ""})

    return out


def convert_request_to_openai(
    anthropic_request: AnthropicMessageRequest,
    target_model: str,
    tool_format: Literal["native", "xml"],
    config: Optional[AdapterConfig] = None,
) -> dict[str, Any]:
    """Convert Anthropic Messages API request to OpenAI Chat Completions format."""
    messages: list[dict[str, Any]] = []

    if anthropic_request.system:
        if isinstance(anthropic_request.system, str):
            system_content = anthropic_request.system
        else:
            system_content = "\n".join(s.text for s in anthropic_request.system)
        system_content = _modify_system_prompt_for_adapter(system_content)
        messages.append({"role": "system", "content": system_content})

    if tool_format == "xml" and anthropic_request.tools:
        xml_instructions = generate_xml_tool_instructions(anthropic_request.tools)
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] += "\n\n" + xml_instructions
        else:
            messages.insert(0, {"role": "system", "content": xml_instructions})

    ctx = _IdDeduplicationContext()
    for msg in anthropic_request.messages:
        for m in _convert_message(msg, ctx, tool_format):
            messages.append(m)

    max_tokens = 32 if anthropic_request.max_tokens == 1 else anthropic_request.max_tokens

    LMSTUDIO_DEFAULT_CTX = 4096
    effective_ctx: Optional[int] = None
    preset = None
    if config and config.provider:
        preset = get_provider_preset(config.provider)
        if config.provider == "lmstudio":
            effective_ctx = config.max_context_window if config.max_context_window is not None else LMSTUDIO_DEFAULT_CTX
        else:
            effective_ctx = config.max_context_window if config.max_context_window is not None else (preset.max_context_window if preset else None)

    if effective_ctx and effective_ctx > 0:
        reserve = CONTEXT_RESERVE_TOKENS
        max_tokens_cap = max(256, effective_ctx - reserve)
        if max_tokens > max_tokens_cap:
            max_tokens = max_tokens_cap
            logger.debug(f"Limited max_tokens to {max_tokens} (context window {effective_ctx})")
        max_prompt_tokens = max(0, effective_ctx - max_tokens - reserve)
        if max_prompt_tokens > 0:
            orig_len = len(messages)
            messages = _truncate_messages_to_fit(messages, max_prompt_tokens)
            if len(messages) < orig_len:
                logger.info(
                    f"Truncated messages to fit context window "
                    f"(kept {len(messages)}/{orig_len}, max_prompt_tokens={max_prompt_tokens})"
                )

    openai_request: dict[str, Any] = {
        "model": target_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": anthropic_request.stream or False,
    }
    if anthropic_request.stream:
        openai_request["stream_options"] = {"include_usage": True}
    if anthropic_request.temperature is not None:
        openai_request["temperature"] = anthropic_request.temperature
    if tool_format == "xml":
        openai_request["temperature"] = 0
    if anthropic_request.top_p is not None:
        openai_request["top_p"] = anthropic_request.top_p
    if anthropic_request.stop_sequences:
        openai_request["stop"] = anthropic_request.stop_sequences
    if tool_format == "native" and anthropic_request.tools:
        openai_request["tools"] = [t.model_dump() for t in convert_tools_to_openai(anthropic_request.tools)]
    if tool_format == "native" and anthropic_request.tool_choice:
        openai_request["tool_choice"] = convert_tool_choice_to_openai(anthropic_request.tool_choice)

    return openai_request
