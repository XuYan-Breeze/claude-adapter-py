"""Request converter 请求转换器

Convert Anthropic Messages API requests to OpenAI Chat Completions format
将 Anthropic Messages API 请求转换为 OpenAI Chat Completions 格式
"""

import json
import secrets
import string
from typing import Any, Literal, Optional

from ..models.anthropic import (
    AnthropicMessageRequest,
    AnthropicMessage,
    AnthropicContentBlock,
    AnthropicTextBlock,
    AnthropicToolUseBlock,
    AnthropicToolResultBlock,
    AnthropicThinkingBlock,
    AnthropicRedactedThinkingBlock,
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
MIN_COMPLETION_TOKENS = 32


def _estimate_tokens(text: str) -> int:
    """Rough token count estimate (conservative: ~2 chars per token)."""
    if not text:
        return 0
    return max(1, (len(text) + 1) // 2)


def _estimate_message_tokens(msg: dict[str, Any]) -> int:
    """Estimate token count for one OpenAI-format message."""
    total = 8

    content = msg.get("content")
    if isinstance(content, str):
        total += _estimate_tokens(content)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and "text" in part and isinstance(part["text"], str):
                total += _estimate_tokens(part["text"])
            else:
                total += 2
    elif content is not None:
        total += _estimate_tokens(str(content))

    tool_call_id = msg.get("tool_call_id")
    if isinstance(tool_call_id, str):
        total += _estimate_tokens(tool_call_id) + 4

    tool_calls = msg.get("tool_calls")
    if isinstance(tool_calls, list):
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                total += 8
                continue
            tc_id = tool_call.get("id")
            if isinstance(tc_id, str):
                total += _estimate_tokens(tc_id)
            function = tool_call.get("function")
            if isinstance(function, dict):
                name = function.get("name")
                arguments = function.get("arguments")
                if isinstance(name, str):
                    total += _estimate_tokens(name)
                if isinstance(arguments, str):
                    total += _estimate_tokens(arguments)
            total += 8

    return total


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


def _resolve_effective_context_window(
    config: Optional[AdapterConfig],
    preset_max_context_window: Optional[int],
    target_model: str,
) -> Optional[int]:
    """Resolve the usable context window for prompt truncation."""
    if config and config.max_context_window is not None and config.max_context_window > 0:
        return config.max_context_window
    if preset_max_context_window is not None and preset_max_context_window > 0:
        return preset_max_context_window

    model_name = target_model.lower()
    if config and config.provider == "nvidia" and "gpt-oss" in model_name:
        return 131072
    return None


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


_PREFILL_TOKENS = frozenset(["{", "[", "```", '{"', "[{", "<", "<tool_code", "<tool_code>"])


def _is_assistant_prefill(content: str) -> bool:
    """Detect Anthropic-specific assistant prefill tokens that other providers don't support."""
    trimmed = content.strip()
    if trimmed in _PREFILL_TOKENS or len(trimmed) <= 2:
        return True
    if trimmed.startswith("<tool_code") and "</tool_code>" not in trimmed:
        return True
    return False


class _IdDeduplicationContext:
    def __init__(self) -> None:
        self.seen_ids: set[str] = set()
        self.id_mappings: dict[str, list[str]] = {}
        self.result_index: dict[str, int] = {}


_ID_CHARS = string.ascii_letters + string.digits


def _deduplicate_tool_id(tool_id: str, ctx: _IdDeduplicationContext) -> str:
    """Deduplicate tool ID for OpenAI (unique per request).

    When a duplicate ID is detected, generates a new random ID (keeping
    the first 8 chars of the original if long enough) and records the
    mapping so that later tool_result messages can find the correct ID.
    """
    id_to_use = tool_id

    if tool_id in ctx.seen_ids:
        orig_len = len(tool_id)
        if orig_len > 11:
            id_to_use = tool_id[:8] + "".join(
                secrets.choice(_ID_CHARS) for _ in range(orig_len - 8)
            )
        else:
            id_to_use = "".join(
                secrets.choice(_ID_CHARS) for _ in range(orig_len)
            )

    ctx.seen_ids.add(id_to_use)

    if tool_id not in ctx.id_mappings:
        ctx.id_mappings[tool_id] = []
    ctx.id_mappings[tool_id].append(id_to_use)

    return id_to_use


def _resolve_tool_result_id(tool_use_id: str, ctx: _IdDeduplicationContext) -> str:
    """Resolve the deduplicated ID for a tool_result reference."""
    if tool_use_id in ctx.id_mappings:
        mappings = ctx.id_mappings[tool_use_id]
        idx = ctx.result_index.get(tool_use_id, 0)
        if idx < len(mappings):
            ctx.result_index[tool_use_id] = idx + 1
            return mappings[idx]
    return tool_use_id


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
            tool_results: list[tuple[str, str, bool]] = []
            for block in content:
                if isinstance(block, AnthropicTextBlock):
                    text_parts.append(block.text)
                elif isinstance(block, AnthropicToolResultBlock):
                    c = block.content
                    if isinstance(c, str):
                        c_str = c
                    elif isinstance(c, list):
                        c_str = "\n".join(
                            part["text"]
                            for part in c
                            if isinstance(part, dict) and part.get("type") == "text" and "text" in part
                        )
                    else:
                        c_str = ""
                    is_error = getattr(block, "is_error", False) or False
                    tool_results.append((block.tool_use_id, c_str, is_error))

            if tool_format == "xml":
                flat_content = ""
                for part in text_parts:
                    flat_content += part

                if tool_results:
                    xml_results = "\n\n".join(
                        f"<tool_output>\n{c}\n</tool_output>"
                        for _, c, _ in tool_results
                    )
                    if flat_content:
                        flat_content += "\n\n"
                    flat_content += xml_results

                if flat_content:
                    out.append({"role": "user", "content": flat_content})
            else:
                # Native mode: tool results become separate tool messages
                result_msgs: list[dict[str, Any]] = []
                for tid, c, is_error in tool_results:
                    result_msgs.append({
                        "role": "tool",
                        "content": f"Error: {c}" if is_error else c,
                        "tool_call_id": _resolve_tool_result_id(tid, ctx),
                    })
                out.extend(result_msgs)

                if text_parts:
                    if len(text_parts) == 1:
                        out.append({"role": "user", "content": text_parts[0]})
                    else:
                        out.append({
                            "role": "user",
                            "content": [{"type": "text", "text": t} for t in text_parts],
                        })

    elif msg.role == "assistant":
        if isinstance(content, str):
            if _is_assistant_prefill(content):
                return out
            out.append({"role": "assistant", "content": content or ""})
        else:
            text_parts: list[str] = []
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

            if not tool_calls and _is_assistant_prefill(content_str):
                return out

            if tool_format == "xml":
                full_content = content_str or ""
                if tool_calls:
                    xml_tool_calls = "\n\n".join(
                        f'<tool_code name="{tc["function"]["name"]}">\n'
                        f'{tc["function"]["arguments"]}\n</tool_code>'
                        for tc in tool_calls
                    )
                    if full_content:
                        full_content += "\n\n"
                    full_content += xml_tool_calls
                out.append({"role": "assistant", "content": full_content})
            else:
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": content_str or None,
                }
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                out.append(assistant_msg)

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

    max_tokens = MIN_COMPLETION_TOKENS if anthropic_request.max_tokens == 1 else anthropic_request.max_tokens

    LMSTUDIO_DEFAULT_CTX = 4096
    effective_ctx: Optional[int] = None
    preset = None
    if config and config.provider:
        preset = get_provider_preset(config.provider)
        if config.provider == "lmstudio":
            effective_ctx = config.max_context_window if config.max_context_window is not None else LMSTUDIO_DEFAULT_CTX
        else:
            effective_ctx = _resolve_effective_context_window(
                config,
                preset.max_context_window if preset else None,
                target_model,
            )

    if effective_ctx and effective_ctx > 0:
        reserve = CONTEXT_RESERVE_TOKENS
        prompt_tokens = sum(_estimate_message_tokens(m) for m in messages)
        prompt_tokens_before = prompt_tokens
        message_count_before = len(messages)
        available_completion_tokens = effective_ctx - prompt_tokens - reserve
        truncated = False

        if available_completion_tokens <= 0:
            target_completion_tokens = min(
                max_tokens,
                max(MIN_COMPLETION_TOKENS, max(1, effective_ctx // 8)),
            )
            max_prompt_tokens = max(1, effective_ctx - target_completion_tokens - reserve)
            orig_len = len(messages)
            messages = _truncate_messages_to_fit(messages, max_prompt_tokens)
            if len(messages) < orig_len:
                truncated = True
                logger.info(
                    f"Truncated messages to fit context window "
                    f"(kept {len(messages)}/{orig_len}, max_prompt_tokens={max_prompt_tokens})"
                )
            prompt_tokens = sum(_estimate_message_tokens(m) for m in messages)
            available_completion_tokens = effective_ctx - prompt_tokens - reserve

        max_tokens_cap = max(1, available_completion_tokens)
        if max_tokens > max_tokens_cap:
            max_tokens = max_tokens_cap
            logger.debug(f"Limited max_tokens to {max_tokens} (context window {effective_ctx})")

        if truncated:
            logger.info(
                "Context budgeting summary",
                {
                    "ctx": effective_ctx,
                    "reserve": reserve,
                    "messages_before": message_count_before,
                    "messages_after": len(messages),
                    "prompt_tokens_before": prompt_tokens_before,
                    "prompt_tokens_after": prompt_tokens,
                    "available_completion_tokens": max(1, available_completion_tokens),
                    "final_max_tokens": max_tokens,
                },
            )

    max_tokens = max(1, max_tokens)

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
