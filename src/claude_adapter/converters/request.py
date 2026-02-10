"""Request converter 请求转换器

Convert Anthropic Messages API requests to OpenAI Chat Completions format
将 Anthropic Messages API 请求转换为 OpenAI Chat Completions 格式
"""

import json
import random
import string
from typing import Any, Literal, Optional, Union
from pydantic import BaseModel

from ..models.anthropic import (
    AnthropicMessageRequest,
    AnthropicMessage,
    AnthropicContentBlock,
    AnthropicSystemContent,
    AnthropicTextBlock,
    AnthropicToolUseBlock,
    AnthropicToolResultBlock,
)
from ..models.openai import (
    OpenAIChatRequest,
    OpenAIMessage,
    OpenAISystemMessage,
    OpenAIUserMessage,
    OpenAIAssistantMessage,
    OpenAIToolMessage,
    OpenAITextContentPart,
    OpenAIToolCall,
)
from ..models.config import AdapterConfig
from .tools import convert_tools_to_openai, convert_tool_choice_to_openai
from .xml_prompt import generate_xml_tool_instructions
from ..utils.update import get_cached_update_info
from ..utils.metadata import CURRENT_VERSION
from ..providers import get_provider_preset

# Claude Code identifier for branding Claude Code 标识符用于品牌化
CLAUDE_CODE_IDENTIFIER = "You are Claude Code, Anthropic's official CLI for Claude."


def _modify_system_prompt_for_adapter(system_content: str) -> str:
    """Modify system prompt to replace Claude Code identifier
    修改系统提示以替换 Claude Code 标识符
    
    Args:
        system_content: Original system content 原始系统内容
        
    Returns:
        Modified system content 修改后的系统内容
    """
    if CLAUDE_CODE_IDENTIFIER not in system_content:
        return system_content
    
    # Check for updates 检查更新
    update_info = get_cached_update_info()
    
    replacement = (
        f"You are Claude Code, running on Claude Adapter Python V{CURRENT_VERSION} "
        "(https://github.com/your-repo/claude-adapter-py). "
        "When introducing yourself or greeting, mention Claude Adapter."
    )
    
    # Add update notification if available 如果有更新则添加更新通知
    if update_info and update_info.has_update:
        replacement += (
            f" IMPORTANT: A new version is available ({update_info.current} → {update_info.latest}). "
            "Request permission to run 'pip install --upgrade claude-adapter-py' to update."
        )
    
    return system_content.replace(CLAUDE_CODE_IDENTIFIER, replacement)


def _is_assistant_prefill(content: str) -> bool:
    """Check if content is an assistant prefill token
    检查内容是否为助手预填充令牌
    
    Anthropic supports prefilling assistant responses, but other providers don't
    Anthropic 支持预填充助手响应，但其他提供商不支持
    
    Args:
        content: Content to check 要检查的内容
        
    Returns:
        True if it's a prefill token 如果是预填充令牌则为 True
    """
    prefill_tokens = ["{", "[", "```", '{"', "[{", "<", "<tool_code", "<tool_code>"]
    trimmed = content.strip()
    
    # Check common prefill tokens or very short content 检查常见预填充令牌或非常短的内容
    if trimmed in prefill_tokens or len(trimmed) <= 2:
        return True
    
    # Special handling for XML tool calling prefill XML 工具调用预填充的特殊处理
    if trimmed.startswith("<tool_code") and "</tool_code>" not in trimmed:
        return True
    
    return False


class _IdDeduplicationContext:
    """Context for tracking tool ID deduplication across messages
    跨消息跟踪工具 ID 去重的上下文
    
    Attributes:
        seen_ids: Set of seen IDs 已见 ID 集合
        id_mappings: Original ID -> deduplicated IDs 原始 ID -> 去重 ID
        result_index: Tracks which mapping to use 跟踪使用哪个映射
    """

    def __init__(self):
        self.seen_ids: set[str] = set()
        self.id_mappings: dict[str, list[str]] = {}
        self.result_index: dict[str, int] = {}


def _deduplicate_tool_id(tool_id: str, ctx: _IdDeduplicationContext) -> str:
    """Deduplicate tool ID if already seen 如果已见则去重工具 ID
    
    Args:
        tool_id: Original tool ID 原始工具 ID
        ctx: Deduplication context 去重上下文
        
    Returns:
        Unique tool ID 唯一工具 ID
    """
    if tool_id not in ctx.seen_ids:
        ctx.seen_ids.add(tool_id)
        return tool_id
    
    # Generate unique ID 生成唯一 ID
    chars = string.ascii_letters + string.digits
    original_len = len(tool_id)
    
    if original_len > 11:
        # Keep first 8 chars, randomize the rest 保留前 8 个字符，随机化其余部分
        new_id = tool_id[:8] + "".join(random.choices(chars, k=original_len - 8))
    else:
        # Generate entirely new ID of same length 生成相同长度的全新 ID
        new_id = "".join(random.choices(chars, k=original_len))
    
    print(f"[adapter] Repair ID: {tool_id} → {new_id}")
    ctx.seen_ids.add(new_id)
    
    # Track mapping 跟踪映射
    if tool_id not in ctx.id_mappings:
        ctx.id_mappings[tool_id] = []
    ctx.id_mappings[tool_id].append(new_id)
    
    return new_id


def _process_user_content_blocks(
    blocks: list[AnthropicContentBlock], ctx: _IdDeduplicationContext
) -> tuple[list[OpenAITextContentPart], list[OpenAIToolMessage]]:
    """Process user content blocks, separating tool results from regular content
    处理用户内容块，将工具结果与常规内容分离
    
    Args:
        blocks: Content blocks 内容块列表
        ctx: Deduplication context 去重上下文
        
    Returns:
        (user_content, tool_results) tuple (用户内容, 工具结果) 元组
    """
    user_content: list[OpenAITextContentPart] = []
    tool_results: list[OpenAIToolMessage] = []
    
    for block in blocks:
        if isinstance(block, AnthropicTextBlock):
            user_content.append(OpenAITextContentPart(type="text", text=block.text))
        elif isinstance(block, AnthropicToolResultBlock):
            # Extract content 提取内容
            if isinstance(block.content, str):
                content = block.content
            elif isinstance(block.content, list):
                content = "\n".join([
                    c.get("text", "") for c in block.content if c.get("type") == "text"
                ])
            else:
                content = ""
            
            # Look up deduplicated ID 查找去重 ID
            tool_call_id = block.tool_use_id
            if block.tool_use_id in ctx.id_mappings:
                mappings = ctx.id_mappings[block.tool_use_id]
                idx = ctx.result_index.get(block.tool_use_id, 0)
                if idx < len(mappings):
                    tool_call_id = mappings[idx]
                    ctx.result_index[block.tool_use_id] = idx + 1
            
            # Add error prefix if needed 如有需要添加错误前缀
            if block.is_error:
                content = f"Error: {content}"
            
            tool_results.append(
                OpenAIToolMessage(role="tool", tool_call_id=tool_call_id, content=content)
            )
    
    return user_content, tool_results


def _process_assistant_content_blocks(
    blocks: list[AnthropicContentBlock], ctx: _IdDeduplicationContext
) -> tuple[str, list[dict[str, Any]]]:
    """Process assistant content blocks, extracting text and tool calls
    处理助手内容块，提取文本和工具调用
    
    Deduplicates tool IDs to prevent errors with providers that reject duplicates
    去重工具 ID 以防止提供商拒绝重复 ID 的错误
    
    Args:
        blocks: Content blocks 内容块列表
        ctx: Deduplication context 去重上下文
        
    Returns:
        (text_content, tool_calls) tuple (文本内容, 工具调用) 元组
    """
    text_content = ""
    tool_calls: list[dict[str, Any]] = []
    
    for block in blocks:
        if isinstance(block, AnthropicTextBlock):
            text_content += block.text
        elif isinstance(block, AnthropicToolUseBlock):
            # Deduplicate ID 去重 ID
            id_to_use = _deduplicate_tool_id(block.id, ctx)
            
            tool_calls.append({
                "id": id_to_use,
                "type": "function",
                "function": {
                    "name": block.name,
                    "arguments": json.dumps(block.input, ensure_ascii=False),
                },
            })
    
    return text_content, tool_calls


def _convert_message(
    msg: AnthropicMessage,
    ctx: _IdDeduplicationContext,
    tool_format: Literal["native", "xml"],
) -> list[Union[OpenAIMessage, dict[str, Any]]]:
    """Convert a single Anthropic message to OpenAI format
    将单个 Anthropic 消息转换为 OpenAI 格式
    
    May return multiple messages (e.g., tool results become separate messages)
    可能返回多个消息（例如，工具结果成为单独的消息）
    
    Args:
        msg: Anthropic message Anthropic 消息
        ctx: Deduplication context 去重上下文
        tool_format: Tool calling format 工具调用格式
        
    Returns:
        List of OpenAI messages OpenAI 消息列表
    """
    result: list[Union[OpenAIMessage, dict[str, Any]]] = []
    
    # Handle string content 处理字符串内容
    if isinstance(msg.content, str):
        if msg.role == "user":
            result.append(OpenAIUserMessage(role="user", content=msg.content))
        else:
            # Skip assistant prefill messages 跳过助手预填充消息
            if not _is_assistant_prefill(msg.content):
                result.append(OpenAIAssistantMessage(role="assistant", content=msg.content))
        return result
    
    # Handle content blocks 处理内容块
    if msg.role == "user":
        user_content, tool_results = _process_user_content_blocks(msg.content, ctx)
        
        if tool_format == "xml":
            # XML Mode: Flatten tool results into user message text
            # XML 模式：将工具结果扁平化到用户消息文本中
            flat_content = ""
            
            # Add regular user text 添加常规用户文本
            for part in user_content:
                flat_content += part.text
            
            # Add tool results as XML blocks 将工具结果添加为 XML 块
            if tool_results:
                xml_results = "\n\n".join([
                    f"<tool_output>\n{tr.content}\n</tool_output>"
                    for tr in tool_results
                ])
                if flat_content:
                    flat_content += "\n\n"
                flat_content += xml_results
            
            if flat_content:
                result.append(OpenAIUserMessage(role="user", content=flat_content))
        else:
            # Native Mode: Standard separation
            # 原生模式：标准分离
            result.extend(tool_results)  # type: ignore
            
            if user_content:
                if len(user_content) == 1:
                    result.append(OpenAIUserMessage(role="user", content=user_content[0].text))
                else:
                    result.append(OpenAIUserMessage(role="user", content=user_content))  # type: ignore
    
    else:  # Assistant message 助手消息
        text_content, tool_calls = _process_assistant_content_blocks(msg.content, ctx)
        
        # Skip assistant prefill 跳过助手预填充
        if not tool_calls and text_content and _is_assistant_prefill(text_content):
            return result
        
        if tool_format == "xml":
            # XML Mode: Reconstruct XML tags from tool calls
            # XML 模式：从工具调用重建 XML 标签
            full_content = text_content or ""
            
            if tool_calls:
                xml_tool_calls = "\n\n".join([
                    f'<tool_code name="{tc["function"]["name"]}">\n'
                    f'{tc["function"]["arguments"]}\n'
                    f'</tool_code>'
                    for tc in tool_calls
                ])
                if full_content:
                    full_content += "\n\n"
                full_content += xml_tool_calls
            
            result.append(OpenAIAssistantMessage(role="assistant", content=full_content))
        else:
            # Native Mode: Standard fields 原生模式：标准字段
            assistant_msg = OpenAIAssistantMessage(
                role="assistant",
                content=text_content or None,
                tool_calls=[OpenAIToolCall(**tc) for tc in tool_calls] if tool_calls else None,
            )
            result.append(assistant_msg)
    
    return result


def convert_request_to_openai(
    anthropic_request: AnthropicMessageRequest,
    target_model: str,
    tool_format: Literal["native", "xml"] = "native",
    config: Optional[AdapterConfig] = None,
) -> dict[str, Any]:
    """Convert Anthropic Messages API request to OpenAI Chat Completions format
    将 Anthropic Messages API 请求转换为 OpenAI Chat Completions 格式
    
    Args:
        anthropic_request: Anthropic request Anthropic 请求
        target_model: Target model name 目标模型名称
        tool_format: Tool calling format 工具调用格式
        config: Adapter configuration 适配器配置
        
    Returns:
        OpenAI request dict OpenAI 请求字典
    """
    messages: list[dict[str, Any]] = []
    
    # Handle system prompt 处理系统提示
    if anthropic_request.system:
        if isinstance(anthropic_request.system, str):
            system_content = anthropic_request.system
        else:
            # Join multiple system content blocks 连接多个系统内容块
            system_content = "\n".join([
                s.text for s in anthropic_request.system
            ])
        
        # Apply branding modification 应用品牌化修改
        system_content = _modify_system_prompt_for_adapter(system_content)
        
        messages.append({"role": "system", "content": system_content})
    
    # XML mode: inject tool instructions into system prompt
    # XML 模式：将工具指令注入系统提示
    if tool_format == "xml" and anthropic_request.tools:
        xml_instructions = generate_xml_tool_instructions(anthropic_request.tools)
        if messages and messages[0]["role"] == "system":
            messages[0]["content"] += "\n\n" + xml_instructions
        else:
            messages.insert(0, {"role": "system", "content": xml_instructions})
    
    # Track tool ID deduplication 跟踪工具 ID 去重
    ctx = _IdDeduplicationContext()
    
    # Convert messages 转换消息
    for msg in anthropic_request.messages:
        converted = _convert_message(msg, ctx, tool_format)
        for m in converted:
            if isinstance(m, BaseModel):
                messages.append(m.model_dump(exclude_none=True))
            else:
                messages.append(m)
    
    # Handle max_tokens 处理 max_tokens
    # Azure OpenAI validation fix: convert 1 to 32
    # Azure OpenAI 验证修复：将 1 转换为 32
    max_tokens = 32 if anthropic_request.max_tokens == 1 else anthropic_request.max_tokens
    
    # Limit max_tokens for local models with restricted context windows
    # 限制本地模型的 max_tokens 以防止上下文窗口限制
    if config and config.provider:
        preset = get_provider_preset(config.provider)
        if preset.max_context_window and max_tokens:
            max_allowed = int(preset.max_context_window * 0.9)
            if max_tokens > max_allowed:
                max_tokens = max_allowed
                print(
                    f"[adapter] Limited max_tokens to {max_tokens} "
                    f"(model context window: {preset.max_context_window})"
                )
    
    # Build OpenAI request 构建 OpenAI 请求
    openai_request: dict[str, Any] = {
        "model": target_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": anthropic_request.stream or False,
    }
    
    # Add stream options for usage data 为使用数据添加流选项
    if anthropic_request.stream:
        openai_request["stream_options"] = {"include_usage": True}
    
    # Optional parameters 可选参数
    if anthropic_request.temperature is not None:
        openai_request["temperature"] = anthropic_request.temperature
    
    # XML mode: force temperature=0 for deterministic output
    # XML 模式：强制 temperature=0 以获得确定性输出
    if tool_format == "xml":
        openai_request["temperature"] = 0
    
    if anthropic_request.top_p is not None:
        openai_request["top_p"] = anthropic_request.top_p
    
    if anthropic_request.stop_sequences:
        openai_request["stop"] = anthropic_request.stop_sequences
    
    # Convert tools (only in native mode) 转换工具（仅在原生模式下）
    if tool_format == "native" and anthropic_request.tools:
        openai_request["tools"] = [
            t.model_dump() for t in convert_tools_to_openai(anthropic_request.tools)
        ]
    
    if tool_format == "native" and anthropic_request.tool_choice:
        openai_request["tool_choice"] = convert_tool_choice_to_openai(
            anthropic_request.tool_choice
        )
    
    return openai_request
