"""Messages handler 消息处理器

Handle /v1/messages API requests
处理 /v1/messages API 请求
"""

import json
import secrets
from typing import Any
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
from openai import AsyncOpenAI

from ..models.anthropic import AnthropicMessageRequest, AnthropicUsage
from ..models.config import AdapterConfig
from ..converters.request import convert_request_to_openai
from ..converters.response import create_error_response
from ..converters.streaming import convert_stream_to_anthropic
from ..utils.logger import logger
from ..utils.validation import validate_anthropic_request, format_validation_errors
from ..utils.token_usage import record_usage
from ..utils.error_log import record_error
from openai import APIError as OpenAIAPIError


def _generate_request_id() -> str:
    """Generate a unique request ID 生成唯一请求 ID

    Returns:
        Request ID (format: msg_XXXXXXXXXXXXXXXXXXXX)
        请求 ID（格式：msg_XXXXXXXXXXXXXXXXXXXX）
    """
    return f"msg_{secrets.token_urlsafe(18)[:24]}"


def _detect_tool_format(anthropic_request: AnthropicMessageRequest, config: AdapterConfig) -> str:
    """Detect which tool format to use 检测使用哪种工具格式

    Args:
        anthropic_request: Anthropic request Anthropic 请求
        config: Adapter configuration 适配器配置

    Returns:
        Tool format ("native" or "xml") 工具格式（"native" 或 "xml"）
    """
    # If no tools in request, format doesn't matter 如果请求中没有工具，格式无关紧要
    if not anthropic_request.tools:
        return "native"

    # Use configured tool format 使用配置的工具格式
    return config.tool_format


def _map_finish_reason(finish_reason: str | None) -> str | None:
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
        "content_filter": "end_turn",
    }
    return mapping.get(finish_reason, "end_turn")


def _convert_openai_response_to_anthropic(
    openai_response: Any,
    original_model_requested: str,
) -> dict[str, Any]:
    """Convert OpenAI SDK response object to Anthropic dict
    将 OpenAI SDK 响应对象转换为 Anthropic 字典

    Works directly with the openai SDK ChatCompletion object
    直接使用 openai SDK ChatCompletion 对象

    Args:
        openai_response: Response from openai SDK openai SDK 的响应
        original_model_requested: Original model name 原始模型名称

    Returns:
        Anthropic response dict Anthropic 响应字典
    """
    choice = openai_response.choices[0]
    message = choice.message

    # Build content blocks 构建内容块
    content: list[dict[str, Any]] = []

    # Add text content if present 如果存在则添加文本内容
    if message.content:
        content.append({"type": "text", "text": message.content})

    # Add tool use blocks if present 如果存在则添加工具使用块
    if message.tool_calls:
        for tool_call in message.tool_calls:
            # Parse arguments JSON 解析参数 JSON
            try:
                input_data = json.loads(tool_call.function.arguments)
            except (json.JSONDecodeError, AttributeError):
                input_data = {"raw": getattr(tool_call.function, "arguments", "")}

            content.append({
                "type": "tool_use",
                "id": tool_call.id,
                "name": tool_call.function.name,
                "input": input_data,
            })

    # Map finish reason 映射完成原因
    stop_reason = _map_finish_reason(choice.finish_reason)

    # Build usage - handle both attribute and dict access
    # 构建使用统计 - 处理属性和字典访问
    usage = openai_response.usage
    input_tokens = getattr(usage, "prompt_tokens", 0)
    output_tokens = getattr(usage, "completion_tokens", 0)

    # Check for cached tokens 检查缓存 token
    cached_tokens = None
    if hasattr(usage, "prompt_tokens_details") and usage.prompt_tokens_details:
        cached_tokens = getattr(usage.prompt_tokens_details, "cached_tokens", None)

    usage_dict: dict[str, Any] = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    if cached_tokens:
        usage_dict["cache_read_input_tokens"] = cached_tokens

    return {
        "id": f"msg_{openai_response.id}",
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": original_model_requested,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": usage_dict,
    }


async def handle_messages_request(
    request: Request,
    config: AdapterConfig,
) -> Any:
    """Handle POST /v1/messages requests 处理 POST /v1/messages 请求

    Args:
        request: FastAPI request FastAPI 请求
        config: Adapter configuration 适配器配置

    Returns:
        JSON or streaming response JSON 或流式响应
    """
    # Generate request ID 生成请求 ID
    request_id = _generate_request_id()
    req_logger = logger.with_request_id(request_id)

    try:
        # Parse request body 解析请求体
        body = await request.json()

        # Validate request 验证请求
        validation_result = validate_anthropic_request(body)
        if not validation_result.valid:
            error_msg = format_validation_errors(validation_result.errors)
            req_logger.error(f"Validation failed: {error_msg}")
            return JSONResponse(
                status_code=400,
                content=create_error_response(ValueError(error_msg), 400),
            )

        # Parse into Pydantic model 解析为 Pydantic 模型
        try:
            anthropic_request = AnthropicMessageRequest(**body)
        except Exception as e:
            req_logger.error(f"Failed to parse request: {str(e)}")
            return JSONResponse(
                status_code=400,
                content=create_error_response(e, 400),
            )

        # Detect tool format 检测工具格式
        tool_format = _detect_tool_format(anthropic_request, config)

        # Get target model 获取目标模型
        requested_model = anthropic_request.model
        model_config = config.models

        # Map Claude model names to actual models 将 Claude 模型名称映射到实际模型
        model_mapping = {
            "claude-opus-4-20250514": model_config.opus,
            "claude-opus-4": model_config.opus,
            "claude-3-5-sonnet-20241022": model_config.sonnet,
            "claude-3-5-sonnet": model_config.sonnet,
            "claude-sonnet-4-20250514": model_config.sonnet,
            "claude-sonnet-4": model_config.sonnet,
            "claude-3-5-haiku-20241022": model_config.haiku,
            "claude-3-5-haiku": model_config.haiku,
            "claude-haiku-4-20250514": model_config.haiku,
            "claude-haiku-4": model_config.haiku,
        }

        target_model = model_mapping.get(requested_model, requested_model)

        # Convert request 转换请求
        openai_request = convert_request_to_openai(
            anthropic_request,
            target_model,
            tool_format,  # type: ignore
            config,
        )

        # Initialize OpenAI client 初始化 OpenAI 客户端
        client = AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            http_client=httpx.AsyncClient(timeout=300.0),
        )

        # Handle streaming vs non-streaming 处理流式与非流式
        is_streaming = anthropic_request.stream or False

        # Compact log: one line per request 紧凑日志：每个请求一行
        mode = "stream" if is_streaming else "sync"
        req_logger.info(f"→ {target_model}", {"mode": mode, "tools": tool_format})

        if is_streaming:
            # Streaming response 流式响应

            try:
                # Remove stream from dict to avoid double passing
                # 从字典中移除 stream 以避免重复传递
                stream_request = {k: v for k, v in openai_request.items() if k != "stream"}

                # Create OpenAI stream 创建 OpenAI 流
                openai_stream = await client.chat.completions.create(
                    **stream_request,
                    stream=True,
                )

                # Convert to async iterator of SSE lines 转换为 SSE 行的异步迭代器
                async def openai_line_iterator():
                    try:
                        async for chunk in openai_stream:
                            yield f"data: {chunk.model_dump_json()}\n\n"
                        yield "data: [DONE]\n\n"
                    except OpenAIAPIError as e:
                        # Handle API errors during streaming (e.g., context length exceeded)
                        # 处理流式传输中的 API 错误（例如：超出上下文长度）
                        error_data = {
                            "error": {
                                "type": "invalid_request_error",
                                "message": str(e),
                            }
                        }
                        yield f"data: {json.dumps(error_data)}\n\n"
                        yield "data: [DONE]\n\n"

                # Convert stream to Anthropic format 将流转换为 Anthropic 格式
                anthropic_stream = convert_stream_to_anthropic(
                    openai_line_iterator(),
                    request_id,
                    requested_model,
                )

                return StreamingResponse(
                    anthropic_stream,
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Request-Id": request_id,
                    },
                )
            except Exception as e:
                req_logger.error(f"Streaming error: {str(e)}", error=e)
                record_error(e, request_id, config.base_url, requested_model, True)

                # Extract status code if available 如果可用则提取状态码
                status_code = getattr(e, "status_code", 500)
                return JSONResponse(
                    status_code=status_code,
                    content=create_error_response(e, status_code),
                )

        else:
            # Non-streaming response 非流式响应
            try:
                # Remove stream/stream_options for non-streaming
                # 非流式时移除 stream/stream_options
                non_stream_request = {
                    k: v
                    for k, v in openai_request.items()
                    if k not in ("stream", "stream_options")
                }

                # Call OpenAI API 调用 OpenAI API
                openai_response = await client.chat.completions.create(**non_stream_request)

                # Convert response (using SDK object directly)
                # 转换响应（直接使用 SDK 对象）
                anthropic_response = _convert_openai_response_to_anthropic(
                    openai_response,
                    requested_model,
                )

                # Record usage 记录使用
                usage = anthropic_response["usage"]
                record_usage(
                    provider=config.base_url,
                    model_name=requested_model,
                    model=target_model,
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    cached_input_tokens=usage.get("cache_read_input_tokens"),
                    streaming=False,
                )

                req_logger.info(
                    f"← {target_model}",
                    {"in": usage["input_tokens"], "out": usage["output_tokens"]},
                )

                return JSONResponse(
                    content=anthropic_response,
                    headers={"X-Request-Id": request_id},
                )

            except Exception as e:
                req_logger.error(f"API error: {str(e)}", error=e)
                record_error(e, request_id, config.base_url, requested_model, False)

                # Extract status code 提取状态码
                status_code = getattr(e, "status_code", 500)
                return JSONResponse(
                    status_code=status_code,
                    content=create_error_response(e, status_code),
                )

    except Exception as e:
        req_logger.error(f"Unexpected error: {str(e)}", error=e)
        return JSONResponse(
            status_code=500,
            content=create_error_response(e, 500),
        )
