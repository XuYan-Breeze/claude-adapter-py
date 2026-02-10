"""OpenAI API models OpenAI API 模型

Pydantic models for OpenAI Chat Completions API
OpenAI Chat Completions API 的 Pydantic 模型
"""

from typing import Any, Literal, Optional, Union
from pydantic import BaseModel


# Messages 消息
class OpenAISystemMessage(BaseModel):
    """System message 系统消息"""

    role: Literal["system"] = "system"
    content: str


class OpenAITextContentPart(BaseModel):
    """Text content part 文本内容部分"""

    type: Literal["text"] = "text"
    text: str


class OpenAIImageContentPart(BaseModel):
    """Image content part 图片内容部分"""

    type: Literal["image_url"] = "image_url"
    image_url: dict[str, Any]


class OpenAIUserMessage(BaseModel):
    """User message 用户消息"""

    role: Literal["user"] = "user"
    content: Union[str, list[Union[OpenAITextContentPart, OpenAIImageContentPart]]]


class OpenAIToolCall(BaseModel):
    """Tool call 工具调用"""

    id: str
    type: Literal["function"] = "function"
    function: dict[str, str]  # {name: str, arguments: str}


class OpenAIAssistantMessage(BaseModel):
    """Assistant message 助手消息"""

    role: Literal["assistant"] = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[list[OpenAIToolCall]] = None


class OpenAIToolMessage(BaseModel):
    """Tool message 工具消息"""

    role: Literal["tool"] = "tool"
    content: str
    tool_call_id: str


# Union of all message types 所有消息类型的联合
OpenAIMessage = Union[
    OpenAISystemMessage, OpenAIUserMessage, OpenAIAssistantMessage, OpenAIToolMessage
]


# Tool definitions 工具定义
class OpenAIFunction(BaseModel):
    """Function definition 函数定义"""

    name: str
    description: str
    parameters: dict[str, Any]


class OpenAITool(BaseModel):
    """Tool definition 工具定义"""

    type: Literal["function"] = "function"
    function: OpenAIFunction


class OpenAIToolChoice(BaseModel):
    """Tool choice 工具选择"""

    type: Literal["function"] = "function"
    function: dict[str, str]  # {name: str}


# Request 请求
class OpenAIChatRequest(BaseModel):
    """OpenAI Chat Completions request OpenAI Chat Completions 请求"""

    model: str
    messages: list[OpenAIMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: Optional[int] = None
    stream: Optional[bool] = False
    stream_options: Optional[dict[str, Any]] = None
    stop: Optional[Union[str, list[str]]] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    logit_bias: Optional[dict[str, float]] = None
    user: Optional[str] = None
    tools: Optional[list[OpenAITool]] = None
    tool_choice: Optional[Union[Literal["none", "auto", "required"], OpenAIToolChoice]] = None


# Usage statistics 使用统计
class OpenAIUsage(BaseModel):
    """Token usage statistics Token 使用统计"""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_tokens_details: Optional[dict[str, Any]] = None


# Response 响应
class OpenAIChoice(BaseModel):
    """Response choice 响应选择"""

    index: int
    message: OpenAIAssistantMessage
    finish_reason: Optional[Literal["stop", "length", "tool_calls", "content_filter"]] = None


class OpenAIChatResponse(BaseModel):
    """OpenAI Chat Completions response OpenAI Chat Completions 响应"""

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[OpenAIChoice]
    usage: OpenAIUsage
    system_fingerprint: Optional[str] = None


# Streaming 流式
class OpenAIStreamToolCall(BaseModel):
    """Streaming tool call 流式工具调用"""

    index: int
    id: Optional[str] = None
    type: Optional[Literal["function"]] = None
    function: Optional[dict[str, str]] = None  # {name?: str, arguments?: str}


class OpenAIStreamDelta(BaseModel):
    """Streaming delta 流式增量"""

    role: Optional[Literal["assistant"]] = None
    content: Optional[str] = None
    tool_calls: Optional[list[OpenAIStreamToolCall]] = None


class OpenAIStreamChoice(BaseModel):
    """Streaming choice 流式选择"""

    index: int
    delta: OpenAIStreamDelta
    finish_reason: Optional[Literal["stop", "length", "tool_calls", "content_filter"]] = None


class OpenAIStreamChunk(BaseModel):
    """OpenAI streaming chunk OpenAI 流式数据块"""

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[OpenAIStreamChoice]
    usage: Optional[OpenAIUsage] = None
