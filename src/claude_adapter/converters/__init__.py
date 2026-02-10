"""Converters package 转换器包

Protocol conversion between Anthropic and OpenAI APIs
Anthropic 和 OpenAI API 之间的协议转换
"""

from .request import convert_request_to_openai
from .response import convert_response_to_anthropic, create_error_response
from .tools import convert_tools_to_openai, convert_tool_choice_to_openai, generate_tool_use_id
from .xml_prompt import generate_xml_tool_instructions

__all__ = [
    "convert_request_to_openai",
    "convert_response_to_anthropic",
    "create_error_response",
    "convert_tools_to_openai",
    "convert_tool_choice_to_openai",
    "generate_tool_use_id",
    "generate_xml_tool_instructions",
]
