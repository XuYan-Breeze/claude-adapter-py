"""Request validation 请求验证

Functions for validating Anthropic API requests
验证 Anthropic API 请求的函数
"""

from typing import Any
from pydantic import BaseModel


class ValidationError(BaseModel):
    """Validation error 验证错误
    
    Attributes:
        field: Field name 字段名称
        message: Error message 错误消息
    """

    field: str
    message: str


class ValidationResult(BaseModel):
    """Validation result 验证结果
    
    Attributes:
        valid: Whether valid 是否有效
        errors: List of errors 错误列表
    """

    valid: bool
    errors: list[ValidationError]


def validate_anthropic_request(body: Any) -> ValidationResult:
    """Validate Anthropic Messages API request
    验证 Anthropic Messages API 请求
    
    Args:
        body: Request body 请求体
        
    Returns:
        Validation result 验证结果
    """
    errors: list[ValidationError] = []
    
    if not isinstance(body, dict):
        errors.append(ValidationError(field="body", message="Request body must be an object"))
        return ValidationResult(valid=False, errors=errors)
    
    # Required fields 必需字段
    if "model" not in body or not isinstance(body["model"], str):
        errors.append(ValidationError(field="model", message="model is required and must be a string"))
    
    if "max_tokens" not in body or not isinstance(body["max_tokens"], (int, float)):
        errors.append(ValidationError(field="max_tokens", message="max_tokens is required and must be a number"))
    elif body["max_tokens"] <= 0:
        errors.append(ValidationError(field="max_tokens", message="max_tokens must be a positive number"))
    
    if "messages" not in body or not isinstance(body["messages"], list):
        errors.append(ValidationError(field="messages", message="messages is required and must be an array"))
    elif len(body["messages"]) == 0:
        errors.append(ValidationError(field="messages", message="messages array cannot be empty"))
    else:
        errors.extend(_validate_messages(body["messages"]))
    
    # Optional fields validation 可选字段验证
    if "temperature" in body:
        temp = body["temperature"]
        if not isinstance(temp, (int, float)) or temp < 0 or temp > 1:
            errors.append(
                ValidationError(field="temperature", message="temperature must be a number between 0 and 1")
            )
    
    if "top_p" in body:
        top_p = body["top_p"]
        if not isinstance(top_p, (int, float)) or top_p < 0 or top_p > 1:
            errors.append(ValidationError(field="top_p", message="top_p must be a number between 0 and 1"))
    
    if "stream" in body and not isinstance(body["stream"], bool):
        errors.append(ValidationError(field="stream", message="stream must be a boolean"))

    if "top_k" in body:
        top_k = body["top_k"]
        if not isinstance(top_k, int) or top_k <= 0:
            errors.append(ValidationError(field="top_k", message="top_k must be a positive integer"))

    if "stop_sequences" in body:
        stop_sequences = body["stop_sequences"]
        if not isinstance(stop_sequences, list) or not all(
            isinstance(item, str) for item in stop_sequences
        ):
            errors.append(ValidationError(
                field="stop_sequences",
                message="stop_sequences must be an array of strings",
            ))

    if "metadata" in body and not isinstance(body["metadata"], dict):
        errors.append(ValidationError(field="metadata", message="metadata must be an object"))

    if "system" in body:
        errors.extend(_validate_system(body["system"]))

    if "tools" in body:
        errors.extend(_validate_tools(body["tools"]))

    if "tool_choice" in body:
        errors.extend(_validate_tool_choice(body["tool_choice"], body.get("tools")))
    
    return ValidationResult(valid=len(errors) == 0, errors=errors)


def _validate_messages(messages: list) -> list[ValidationError]:
    """Validate message array structure (matches TS validateMessages)."""
    errors: list[ValidationError] = []

    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            errors.append(ValidationError(
                field=f"messages[{i}]",
                message="message must be an object",
            ))
            continue

        role = msg.get("role")
        if not role or not isinstance(role, str):
            errors.append(ValidationError(
                field=f"messages[{i}].role",
                message="role is required and must be a string",
            ))
        elif role not in ("user", "assistant"):
            errors.append(ValidationError(
                field=f"messages[{i}].role",
                message='role must be "user" or "assistant"',
            ))

        content = msg.get("content")
        if content is None:
            errors.append(ValidationError(
                field=f"messages[{i}].content",
                message="content is required",
            ))
        elif not isinstance(content, (str, list)):
            errors.append(ValidationError(
                field=f"messages[{i}].content",
                message="content must be a string or array",
            ))
        elif isinstance(content, list):
            errors.extend(_validate_content_blocks(content, i, role if isinstance(role, str) else None))

    return errors


def _validate_content_blocks(
    blocks: list,
    message_index: int,
    role: str | None,
) -> list[ValidationError]:
    """Validate content blocks array (matches TS validateContentBlocks)."""
    errors: list[ValidationError] = []

    for j, block in enumerate(blocks):
        if not isinstance(block, dict):
            errors.append(ValidationError(
                field=f"messages[{message_index}].content[{j}]",
                message="content block must be an object",
            ))
            continue

        block_type = block.get("type")
        if not block_type or not isinstance(block_type, str):
            errors.append(ValidationError(
                field=f"messages[{message_index}].content[{j}].type",
                message="content block type is required",
            ))
            continue

        if block_type == "text":
            if not isinstance(block.get("text"), str):
                errors.append(ValidationError(
                    field=f"messages[{message_index}].content[{j}].text",
                    message="text block must contain string field text",
                ))
        elif block_type == "tool_use":
            if role == "user":
                errors.append(ValidationError(
                    field=f"messages[{message_index}].content[{j}]",
                    message='user messages cannot contain "tool_use" blocks',
                ))
            if not isinstance(block.get("id"), str) or not block.get("id"):
                errors.append(ValidationError(
                    field=f"messages[{message_index}].content[{j}].id",
                    message="tool_use.id is required and must be a non-empty string",
                ))
            if not isinstance(block.get("name"), str) or not block.get("name"):
                errors.append(ValidationError(
                    field=f"messages[{message_index}].content[{j}].name",
                    message="tool_use.name is required and must be a non-empty string",
                ))
            if not isinstance(block.get("input"), dict):
                errors.append(ValidationError(
                    field=f"messages[{message_index}].content[{j}].input",
                    message="tool_use.input must be an object",
                ))
        elif block_type == "tool_result":
            if role == "assistant":
                errors.append(ValidationError(
                    field=f"messages[{message_index}].content[{j}]",
                    message='assistant messages cannot contain "tool_result" blocks',
                ))
            if not isinstance(block.get("tool_use_id"), str) or not block.get("tool_use_id"):
                errors.append(ValidationError(
                    field=f"messages[{message_index}].content[{j}].tool_use_id",
                    message="tool_result.tool_use_id is required and must be a non-empty string",
                ))
            content = block.get("content")
            if not isinstance(content, (str, list)):
                errors.append(ValidationError(
                    field=f"messages[{message_index}].content[{j}].content",
                    message="tool_result.content must be a string or array",
                ))
        elif block_type == "thinking":
            if not isinstance(block.get("thinking", ""), str):
                errors.append(ValidationError(
                    field=f"messages[{message_index}].content[{j}].thinking",
                    message="thinking block must contain string field thinking",
                ))
        elif block_type == "redacted_thinking":
            # data is optional, only validate type if present
            if "data" in block and block.get("data") is not None and not isinstance(block.get("data"), str):
                errors.append(ValidationError(
                    field=f"messages[{message_index}].content[{j}].data",
                    message="redacted_thinking.data must be a string",
                ))
        else:
            errors.append(ValidationError(
                field=f"messages[{message_index}].content[{j}].type",
                message=f"unsupported content block type: {block_type}",
            ))

    return errors


def _validate_system(system: Any) -> list[ValidationError]:
    errors: list[ValidationError] = []
    if isinstance(system, str):
        return errors
    if not isinstance(system, list):
        errors.append(ValidationError(
            field="system",
            message="system must be a string or array of text blocks",
        ))
        return errors
    for idx, block in enumerate(system):
        if not isinstance(block, dict):
            errors.append(ValidationError(
                field=f"system[{idx}]",
                message="system block must be an object",
            ))
            continue
        if block.get("type") != "text":
            errors.append(ValidationError(
                field=f"system[{idx}].type",
                message='system block type must be "text"',
            ))
        if not isinstance(block.get("text"), str):
            errors.append(ValidationError(
                field=f"system[{idx}].text",
                message="system block text must be a string",
            ))
    return errors


def _validate_tools(tools: Any) -> list[ValidationError]:
    errors: list[ValidationError] = []
    if tools is None:
        return errors
    if not isinstance(tools, list):
        errors.append(ValidationError(field="tools", message="tools must be an array"))
        return errors
    for idx, tool in enumerate(tools):
        if not isinstance(tool, dict):
            errors.append(ValidationError(
                field=f"tools[{idx}]",
                message="tool definition must be an object",
            ))
            continue
        name = tool.get("name")
        description = tool.get("description")
        schema = tool.get("input_schema")
        if not isinstance(name, str) or not name.strip():
            errors.append(ValidationError(
                field=f"tools[{idx}].name",
                message="tool name is required and must be a non-empty string",
            ))
        if not isinstance(description, str):
            errors.append(ValidationError(
                field=f"tools[{idx}].description",
                message="tool description is required and must be a string",
            ))
        if not isinstance(schema, dict):
            errors.append(ValidationError(
                field=f"tools[{idx}].input_schema",
                message="tool input_schema is required and must be an object",
            ))
        elif schema.get("type") not in (None, "object"):
            errors.append(ValidationError(
                field=f"tools[{idx}].input_schema.type",
                message='tool input_schema.type must be "object" when provided',
            ))
    return errors


def _validate_tool_choice(tool_choice: Any, tools: Any) -> list[ValidationError]:
    errors: list[ValidationError] = []
    if tool_choice is None:
        return errors

    if tools in (None, []):
        errors.append(ValidationError(
            field="tool_choice",
            message="tool_choice requires tools to be provided",
        ))
        return errors

    if isinstance(tool_choice, str):
        if tool_choice not in ("auto", "any"):
            errors.append(ValidationError(
                field="tool_choice",
                message='tool_choice string must be "auto" or "any"',
            ))
        return errors

    if not isinstance(tool_choice, dict):
        errors.append(ValidationError(
            field="tool_choice",
            message='tool_choice must be "auto", "any", or an object',
        ))
        return errors

    choice_type = tool_choice.get("type")
    if choice_type not in ("auto", "any", "tool"):
        errors.append(ValidationError(
            field="tool_choice.type",
            message='tool_choice.type must be "auto", "any", or "tool"',
        ))
        return errors

    if choice_type == "tool":
        if not isinstance(tool_choice.get("name"), str) or not tool_choice.get("name"):
            errors.append(ValidationError(
                field="tool_choice.name",
                message='tool_choice.name is required when type is "tool"',
            ))

    return errors


def format_validation_errors(errors: list[ValidationError]) -> str:
    """Format validation errors as readable string
    将验证错误格式化为可读字符串
    
    Args:
        errors: List of errors 错误列表
        
    Returns:
        Formatted error message 格式化的错误消息
    """
    return "; ".join([f"{err.field}: {err.message}" for err in errors])
