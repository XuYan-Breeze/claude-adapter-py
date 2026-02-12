"""Streaming converters 流式转换器

Convert OpenAI SSE streams to Anthropic SSE events
将 OpenAI SSE 流转换为 Anthropic SSE 事件
"""

import json
from typing import Any, AsyncIterator, Optional

from ..models.openai import OpenAIStreamChunk


class StreamState:
    """State tracker for streaming conversion 流式转换的状态跟踪器
    
    Attributes:
        request_id: Request ID 请求 ID
        model: Model name 模型名称
        content_blocks: Active content blocks 活跃内容块
        tool_calls: Active tool calls 活跃工具调用
        usage: Usage statistics 使用统计
    """

    def __init__(self, request_id: str, model: str):
        self.request_id = request_id
        self.model = model
        self.content_blocks: list[dict[str, Any]] = []
        self.tool_calls: dict[int, dict[str, Any]] = {}
        self.usage: Optional[dict[str, int]] = None


async def convert_stream_to_anthropic(
    openai_stream: AsyncIterator[str],
    request_id: str,
    model: str,
) -> AsyncIterator[str]:
    """Convert OpenAI SSE stream to Anthropic SSE events
    将 OpenAI SSE 流转换为 Anthropic SSE 事件
    
    Args:
        openai_stream: OpenAI SSE stream OpenAI SSE 流
        request_id: Request ID 请求 ID
        model: Model name 模型名称
        
    Yields:
        Anthropic SSE event lines Anthropic SSE 事件行
    """
    state = StreamState(request_id, model)
    
    # Send message_start event 发送 message_start 事件
    yield _format_sse_event("message_start", {
        "type": "message_start",
        "message": {
            "id": request_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    })
    
    # Process stream chunks 处理流数据块
    async for line in openai_stream:
        stripped = line.strip()
        if not stripped or stripped.startswith(":"):
            continue

        if stripped.startswith("data: "):
            data_str = stripped[6:].strip()

            if data_str == "[DONE]":
                break

            try:
                chunk_data = json.loads(data_str)

                # Check for error in chunk - only if it looks like a real API error
                # Only treat as error if error is a dict with message/type fields
                # 检查 chunk 中的错误 - 只在看起来像真正的API错误时才处理
                # 只有当error是包含message/type字段的字典时才视为错误
                if "error" in chunk_data:
                    error = chunk_data["error"]
                    # Only treat as error if it's a dict with required fields
                    # 只在是包含必需字段的字典时才视为错误
                    if isinstance(error, dict) and ("message" in error or "type" in error):
                        error_type = error.get("type", "api_error")
                        error_message = error.get("message", "Unknown error")

                        # Yield error as content block 将错误作为内容块输出
                        error_block_index = len(state.content_blocks)
                        state.content_blocks.append({
                            "type": "text",
                            "text": f"Error: {error_message}",
                        })

                        yield _format_sse_event("content_block_start", {
                            "type": "content_block_start",
                            "index": error_block_index,
                            "content_block": {"type": "text", "text": f"Error: {error_message}"},
                        })

                        yield _format_sse_event("content_block_stop", {
                            "type": "content_block_stop",
                            "index": error_block_index,
                        })

                        yield _format_sse_event("message_delta", {
                            "type": "message_delta",
                            "delta": {"stop_reason": "error", "stop_sequence": None},
                            "usage": state.usage or {"input_tokens": 0, "output_tokens": 0},
                        })

                        yield _format_sse_event("message_stop", {"type": "message_stop"})
                        return

                async for event in _process_chunk(chunk_data, state):
                    yield event
            except json.JSONDecodeError:
                continue
            except Exception as e:
                # 上游畸形 chunk 或解析异常：以错误内容块正常结束流，避免 ASGI 未处理异常
                error_message = str(e)
                error_block_index = len(state.content_blocks)
                state.content_blocks.append({
                    "type": "text",
                    "text": f"Error: {error_message}",
                })
                yield _format_sse_event("content_block_start", {
                    "type": "content_block_start",
                    "index": error_block_index,
                    "content_block": {"type": "text", "text": f"Error: {error_message}"},
                })
                yield _format_sse_event("content_block_stop", {
                    "type": "content_block_stop",
                    "index": error_block_index,
                })
                yield _format_sse_event("message_delta", {
                    "type": "message_delta",
                    "delta": {"stop_reason": "error", "stop_sequence": None},
                    "usage": state.usage or {"input_tokens": 0, "output_tokens": 0},
                })
                yield _format_sse_event("message_stop", {"type": "message_stop"})
                return
    
    # Send message_stop event 发送 message_stop 事件
    if state.usage:
        yield _format_sse_event("message_delta", {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": state.usage,
        })
    
    yield _format_sse_event("message_stop", {"type": "message_stop"})


async def _process_chunk(
    chunk: dict[str, Any],
    state: StreamState,
) -> AsyncIterator[str]:
    """Process a single OpenAI chunk and yield Anthropic events
    处理单个 OpenAI 数据块并生成 Anthropic 事件
    
    Args:
        chunk: OpenAI chunk OpenAI 数据块
        state: Stream state 流状态
        
    Yields:
        Anthropic SSE events Anthropic SSE 事件
    """
    # Check for usage in chunk 检查数据块中的使用统计
    if "usage" in chunk and chunk["usage"]:
        state.usage = {
            "input_tokens": chunk["usage"].get("prompt_tokens", 0),
            "output_tokens": chunk["usage"].get("completion_tokens", 0),
        }
    
    # Process choices 处理选择
    if not chunk.get("choices"):
        return
    
    choice = chunk["choices"][0]
    delta = choice.get("delta", {})
    
    # Handle text content 处理文本内容
    if "content" in delta and delta["content"]:
        content_text = delta["content"]
        
        # Check if we need to start a new text block 检查是否需要开始新的文本块
        if not state.content_blocks or state.content_blocks[-1]["type"] != "text":
            block_index = len(state.content_blocks)
            state.content_blocks.append({"type": "text", "text": ""})
            
            yield _format_sse_event("content_block_start", {
                "type": "content_block_start",
                "index": block_index,
                "content_block": {"type": "text", "text": ""},
            })
        
        # Send text delta 发送文本增量
        block_index = len(state.content_blocks) - 1
        state.content_blocks[block_index]["text"] += content_text
        
        yield _format_sse_event("content_block_delta", {
            "type": "content_block_delta",
            "index": block_index,
            "delta": {"type": "text_delta", "text": content_text},
        })
    
    # Handle tool calls 处理工具调用
    if "tool_calls" in delta and delta["tool_calls"]:
        for tc_delta in delta["tool_calls"]:
            tc_index = tc_delta["index"]
            
            # Start new tool call 开始新的工具调用
            if tc_index not in state.tool_calls:
                state.tool_calls[tc_index] = {
                    "id": tc_delta.get("id", ""),
                    "name": "",
                    "input": "",
                }
                
                block_index = len(state.content_blocks)
                state.content_blocks.append({
                    "type": "tool_use",
                    "id": tc_delta.get("id", ""),
                    "name": "",
                    "input": {},
                })
                
                if "function" in tc_delta and "name" in tc_delta["function"]:
                    name = tc_delta["function"]["name"]
                    state.tool_calls[tc_index]["name"] = name
                    state.content_blocks[block_index]["name"] = name
                
                yield _format_sse_event("content_block_start", {
                    "type": "content_block_start",
                    "index": block_index,
                    "content_block": {
                        "type": "tool_use",
                        "id": tc_delta.get("id", ""),
                        "name": state.tool_calls[tc_index]["name"],
                        "input": {},
                    },
                })
            
            # Update tool call 更新工具调用
            if "function" in tc_delta and "arguments" in tc_delta["function"]:
                args_delta = tc_delta["function"]["arguments"]
                state.tool_calls[tc_index]["input"] += args_delta
                
                # Find the block index by matching tool call ID
                # 通过匹配工具调用 ID 找到块索引
                tc_id = state.tool_calls[tc_index]["id"]
                block_index = next(
                    (i for i, b in enumerate(state.content_blocks)
                     if b.get("type") == "tool_use" and b.get("id") == tc_id),
                    len(state.content_blocks) - 1,  # fallback 回退
                )
                
                yield _format_sse_event("content_block_delta", {
                    "type": "content_block_delta",
                    "index": block_index,
                    "delta": {"type": "input_json_delta", "partial_json": args_delta},
                })
    
    # Handle finish_reason 处理 finish_reason
    if choice.get("finish_reason"):
        # Send content_block_stop for all active blocks 为所有活跃块发送 content_block_stop
        for i in range(len(state.content_blocks)):
            yield _format_sse_event("content_block_stop", {
                "type": "content_block_stop",
                "index": i,
            })


def _format_sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format an SSE event 格式化 SSE 事件
    
    Args:
        event_type: Event type 事件类型
        data: Event data 事件数据
        
    Returns:
        Formatted SSE event 格式化的 SSE 事件
    """
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
