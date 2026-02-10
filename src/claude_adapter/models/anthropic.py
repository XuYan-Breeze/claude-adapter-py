"""Anthropic API models Anthropic API 模型

Pydantic models for Anthropic Messages API
Anthropic Messages API 的 Pydantic 模型
"""

from typing import Annotated, Any, Literal, Optional, Union
from pydantic import BaseModel, Discriminator, Field, Tag


# Content blocks 内容块
class AnthropicTextBlock(BaseModel):
    """Text content block 文本内容块"""

    type: Literal["text"] = "text"
    text: str


class AnthropicToolUseBlock(BaseModel):
    """Tool use content block 工具使用内容块"""

    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class AnthropicToolResultBlock(BaseModel):
    """Tool result content block 工具结果内容块"""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: Union[str, list[dict[str, Any]]]
    is_error: Optional[bool] = None


def _get_content_block_discriminator(v: Any) -> str:
    """Get discriminator value for content block union
    获取内容块联合类型的鉴别值

    Args:
        v: Input value 输入值

    Returns:
        Discriminator tag string 鉴别标签字符串
    """
    if isinstance(v, dict):
        return v.get("type", "text")
    return getattr(v, "type", "text")


# Union of all content block types with discriminator for reliable parsing
# 使用鉴别器的所有内容块类型的联合，确保可靠解析
AnthropicContentBlock = Annotated[
    Union[
        Annotated[AnthropicTextBlock, Tag("text")],
        Annotated[AnthropicToolUseBlock, Tag("tool_use")],
        Annotated[AnthropicToolResultBlock, Tag("tool_result")],
    ],
    Discriminator(_get_content_block_discriminator),
]


# Messages 消息
class AnthropicMessage(BaseModel):
    """Message in conversation 对话中的消息"""

    role: Literal["user", "assistant"]
    content: Union[str, list[AnthropicContentBlock]]


# System content 系统内容
class AnthropicSystemContent(BaseModel):
    """System prompt content 系统提示内容"""

    type: Literal["text"] = "text"
    text: str
    cache_control: Optional[dict[str, Any]] = None


# Tool definitions 工具定义
class AnthropicToolDefinition(BaseModel):
    """Tool definition 工具定义"""

    name: str
    description: str
    input_schema: dict[str, Any]


class AnthropicToolChoice(BaseModel):
    """Tool choice configuration 工具选择配置"""

    type: Literal["auto", "any", "tool"]
    name: Optional[str] = None


# Request 请求
class AnthropicMessageRequest(BaseModel):
    """Anthropic Messages API request Anthropic Messages API 请求"""

    model: str
    messages: list[AnthropicMessage]
    max_tokens: int
    system: Optional[Union[str, list[AnthropicSystemContent]]] = None
    temperature: Optional[float] = Field(None, ge=0, le=1)
    top_p: Optional[float] = Field(None, ge=0, le=1)
    stop_sequences: Optional[list[str]] = None
    stream: Optional[bool] = False
    tools: Optional[list[AnthropicToolDefinition]] = None
    tool_choice: Optional[Union[Literal["auto", "any"], AnthropicToolChoice]] = None
    metadata: Optional[dict[str, Any]] = None


# Usage statistics 使用统计
class AnthropicUsage(BaseModel):
    """Token usage statistics Token 使用统计"""

    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None


# Response 响应
class AnthropicMessageResponse(BaseModel):
    """Anthropic Messages API response Anthropic Messages API 响应"""

    id: str
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    content: list[AnthropicContentBlock]
    model: str
    stop_reason: Optional[Literal["end_turn", "max_tokens", "stop_sequence", "tool_use"]] = None
    stop_sequence: Optional[str] = None
    usage: AnthropicUsage


# Streaming events 流式事件
class AnthropicMessageStartEvent(BaseModel):
    """Message start event 消息开始事件"""

    type: Literal["message_start"] = "message_start"
    message: AnthropicMessageResponse


class AnthropicContentBlockStartEvent(BaseModel):
    """Content block start event 内容块开始事件"""

    type: Literal["content_block_start"] = "content_block_start"
    index: int
    content_block: AnthropicContentBlock


class AnthropicTextDelta(BaseModel):
    """Text delta 文本增量"""

    type: Literal["text_delta"] = "text_delta"
    text: str


class AnthropicInputJsonDelta(BaseModel):
    """Input JSON delta 输入 JSON 增量"""

    type: Literal["input_json_delta"] = "input_json_delta"
    partial_json: str


class AnthropicContentBlockDeltaEvent(BaseModel):
    """Content block delta event 内容块增量事件"""

    type: Literal["content_block_delta"] = "content_block_delta"
    index: int
    delta: Union[AnthropicTextDelta, AnthropicInputJsonDelta]


class AnthropicContentBlockStopEvent(BaseModel):
    """Content block stop event 内容块停止事件"""

    type: Literal["content_block_stop"] = "content_block_stop"
    index: int


class AnthropicMessageDelta(BaseModel):
    """Message delta 消息增量"""

    stop_reason: Optional[Literal["end_turn", "max_tokens", "stop_sequence", "tool_use"]] = None
    stop_sequence: Optional[str] = None


class AnthropicMessageDeltaEvent(BaseModel):
    """Message delta event 消息增量事件"""

    type: Literal["message_delta"] = "message_delta"
    delta: AnthropicMessageDelta
    usage: AnthropicUsage


class AnthropicMessageStopEvent(BaseModel):
    """Message stop event 消息停止事件"""

    type: Literal["message_stop"] = "message_stop"


class AnthropicPingEvent(BaseModel):
    """Ping event 心跳事件"""

    type: Literal["ping"] = "ping"


class AnthropicErrorEvent(BaseModel):
    """Error event 错误事件"""

    type: Literal["error"] = "error"
    error: dict[str, Any]


# Union of all stream events 所有流式事件的联合
AnthropicStreamEvent = Union[
    AnthropicMessageStartEvent,
    AnthropicContentBlockStartEvent,
    AnthropicContentBlockDeltaEvent,
    AnthropicContentBlockStopEvent,
    AnthropicMessageDeltaEvent,
    AnthropicMessageStopEvent,
    AnthropicPingEvent,
    AnthropicErrorEvent,
]
