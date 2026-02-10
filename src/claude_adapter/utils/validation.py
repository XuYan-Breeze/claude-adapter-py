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
    
    return ValidationResult(valid=len(errors) == 0, errors=errors)


def format_validation_errors(errors: list[ValidationError]) -> str:
    """Format validation errors as readable string
    将验证错误格式化为可读字符串
    
    Args:
        errors: List of errors 错误列表
        
    Returns:
        Formatted error message 格式化的错误消息
    """
    return "; ".join([f"{err.field}: {err.message}" for err in errors])
