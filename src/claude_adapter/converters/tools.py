"""Tool calling conversion 工具调用转换

Functions for converting tool definitions between Anthropic and OpenAI formats
在 Anthropic 和 OpenAI 格式之间转换工具定义的函数
"""

import secrets
from typing import Any, Literal, Union

from ..models.anthropic import AnthropicToolDefinition
from ..models.openai import OpenAITool, OpenAIFunction


def convert_tools_to_openai(tools: list[AnthropicToolDefinition]) -> list[OpenAITool]:
    """Convert Anthropic tool definitions to OpenAI function format
    将 Anthropic 工具定义转换为 OpenAI 函数格式
    
    Args:
        tools: Anthropic tool definitions Anthropic 工具定义列表
        
    Returns:
        OpenAI tool definitions OpenAI 工具定义列表
    """
    return [
        OpenAITool(
            type="function",
            function=OpenAIFunction(
                name=tool.name,
                description=tool.description,
                parameters=tool.input_schema,
            ),
        )
        for tool in tools
    ]


def convert_tool_choice_to_openai(
    tool_choice: Union[Literal["auto", "any"], dict[str, Any]]
) -> Union[Literal["none", "auto", "required"], dict[str, Any]]:
    """Convert Anthropic tool choice to OpenAI format
    将 Anthropic 工具选择转换为 OpenAI 格式
    
    Args:
        tool_choice: Anthropic tool choice Anthropic 工具选择
        
    Returns:
        OpenAI tool choice OpenAI 工具选择
    """
    # Handle string types 处理字符串类型
    if isinstance(tool_choice, str):
        if tool_choice == "auto":
            return "auto"
        elif tool_choice == "any":
            return "required"  # OpenAI's equivalent - forces tool use
        else:
            return "auto"
    
    # Handle object type with specific tool 处理带特定工具的对象类型
    if isinstance(tool_choice, dict):
        choice_type = tool_choice.get("type")
        if choice_type == "tool" and "name" in tool_choice:
            return {
                "type": "function",
                "function": {"name": tool_choice["name"]},
            }
        elif choice_type == "auto":
            return "auto"
        elif choice_type == "any":
            return "required"
    
    return "auto"


def generate_tool_use_id() -> str:
    """Generate a unique tool use ID in Anthropic format
    生成 Anthropic 格式的唯一工具使用 ID
    
    Returns:
        Tool use ID (format: toolu_XXXXXXXXXXXXXXXXXXXX)
        工具使用 ID（格式：toolu_XXXXXXXXXXXXXXXXXXXX）
    """
    # Generate 24 random alphanumeric characters 生成 24 个随机字母数字字符
    random_chars = secrets.token_urlsafe(18)[:24]  # Base64 URL-safe, trim to 24
    return f"toolu_{random_chars}"
