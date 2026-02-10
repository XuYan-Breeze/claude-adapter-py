"""Response converter 响应转换器

Convert OpenAI Chat Completions responses to Anthropic Messages format
将 OpenAI Chat Completions 响应转换为 Anthropic Messages 格式
"""

import json
from typing import Any, Literal, Optional

from ..models.anthropic import (
    AnthropicMessageResponse,
    AnthropicContentBlock,
    AnthropicTextBlock,
    AnthropicToolUseBlock,
    AnthropicUsage,
)
from ..models.openai import OpenAIChatResponse, OpenAIToolCall


def _map_finish_reason(
    finish_reason: Optional[str],
) -> Optional[Literal["end_turn", "max_tokens", "stop_sequence", "tool_use"]]:
    """Map OpenAI finish_reason to Anthropic stop_reason
    将 OpenAI finish_reason 映射到 Anthropic stop_reason
    
    Args:
        finish_reason: OpenAI finish reason OpenAI 完成原因
        
    Returns:
        Anthropic stop reason Anthropic 停止原因
    """
    if not finish_reason:
        return None
    
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "end_turn",  # Closest equivalent 最接近的等价物
    }
    
    return mapping.get(finish_reason, "end_turn")  # type: ignore


def _convert_tool_call_to_tool_use(tool_call: OpenAIToolCall) -> AnthropicToolUseBlock:
    """Convert OpenAI tool call to Anthropic tool_use block
    将 OpenAI 工具调用转换为 Anthropic tool_use 块
    
    Args:
        tool_call: OpenAI tool call OpenAI 工具调用
        
    Returns:
        Anthropic tool use block Anthropic 工具使用块
    """
    # Parse arguments JSON 解析参数 JSON
    try:
        input_data = json.loads(tool_call.function["arguments"])
    except (json.JSONDecodeError, KeyError):
        input_data = {"raw": tool_call.function.get("arguments", "")}
    
    return AnthropicToolUseBlock(
        type="tool_use",
        id=tool_call.id,
        name=tool_call.function["name"],
        input=input_data,
    )


def convert_response_to_anthropic(
    openai_response: OpenAIChatResponse,
    original_model_requested: str,
) -> AnthropicMessageResponse:
    """Convert OpenAI Chat Completion response to Anthropic Messages format
    将 OpenAI Chat Completion 响应转换为 Anthropic Messages 格式
    
    Args:
        openai_response: OpenAI response OpenAI 响应
        original_model_requested: Original model name 原始模型名称
        
    Returns:
        Anthropic message response Anthropic 消息响应
    """
    choice = openai_response.choices[0]
    message = choice.message
    
    # Build content blocks 构建内容块
    content: list[AnthropicContentBlock] = []
    
    # Add text content if present 如果存在则添加文本内容
    if message.content:
        content.append(AnthropicTextBlock(type="text", text=message.content))
    
    # Add tool use blocks if present 如果存在则添加工具使用块
    if message.tool_calls:
        for tool_call in message.tool_calls:
            content.append(_convert_tool_call_to_tool_use(tool_call))
    
    # Map finish reason 映射完成原因
    stop_reason = _map_finish_reason(choice.finish_reason)
    
    # Build usage 构建使用统计
    usage = AnthropicUsage(
        input_tokens=openai_response.usage.prompt_tokens,
        output_tokens=openai_response.usage.completion_tokens,
        cache_read_input_tokens=(
            openai_response.usage.prompt_tokens_details.get("cached_tokens")
            if openai_response.usage.prompt_tokens_details
            else None
        ),
    )
    
    return AnthropicMessageResponse(
        id=f"msg_{openai_response.id}",
        type="message",
        role="assistant",
        content=content,
        model=original_model_requested,
        stop_reason=stop_reason,
        stop_sequence=None,
        usage=usage,
    )


def _map_error_type(status_code: int) -> str:
    """Map HTTP status code to Anthropic error type
    将 HTTP 状态码映射到 Anthropic 错误类型
    
    Args:
        status_code: HTTP status code HTTP 状态码
        
    Returns:
        Error type 错误类型
    """
    mapping = {
        400: "invalid_request_error",
        401: "authentication_error",
        403: "permission_error",
        404: "not_found_error",
        429: "rate_limit_error",
        500: "api_error",
    }
    return mapping.get(status_code, "api_error")


def create_error_response(
    error: Exception,
    status_code: int = 500,
) -> dict[str, Any]:
    """Create an error response in Anthropic format
    创建 Anthropic 格式的错误响应
    
    Args:
        error: Exception 异常
        status_code: HTTP status code HTTP 状态码
        
    Returns:
        Error response dict 错误响应字典
    """
    return {
        "error": {
            "type": _map_error_type(status_code),
            "message": str(error),
        },
        "status": status_code,
    }
