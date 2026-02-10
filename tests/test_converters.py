"""Tests for converters 转换器测试

Unit tests for protocol converters
协议转换器的单元测试
"""

import pytest
from claude_adapter.converters.tools import (
    convert_tools_to_openai,
    convert_tool_choice_to_openai,
    generate_tool_use_id,
)
from claude_adapter.converters.xml_prompt import (
    generate_xml_tool_instructions,
    has_xml_tool_instructions,
)
from claude_adapter.models.anthropic import AnthropicToolDefinition


def test_convert_tools_to_openai():
    """Test Anthropic tool definitions conversion to OpenAI format
    测试 Anthropic 工具定义转换为 OpenAI 格式
    """
    anthropic_tools = [
        AnthropicToolDefinition(
            name="read_file",
            description="Read a file",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )
    ]
    
    openai_tools = convert_tools_to_openai(anthropic_tools)
    
    assert len(openai_tools) == 1
    assert openai_tools[0].type == "function"
    assert openai_tools[0].function.name == "read_file"
    assert openai_tools[0].function.description == "Read a file"
    assert openai_tools[0].function.parameters["type"] == "object"


def test_convert_tool_choice_auto():
    """Test tool choice conversion: auto 测试工具选择转换：auto"""
    result = convert_tool_choice_to_openai("auto")
    assert result == "auto"


def test_convert_tool_choice_any():
    """Test tool choice conversion: any 测试工具选择转换：any"""
    result = convert_tool_choice_to_openai("any")
    assert result == "required"


def test_convert_tool_choice_specific():
    """Test tool choice conversion: specific tool 测试工具选择转换：特定工具"""
    result = convert_tool_choice_to_openai({"type": "tool", "name": "read_file"})
    assert isinstance(result, dict)
    assert result["type"] == "function"
    assert result["function"]["name"] == "read_file"


def test_generate_tool_use_id():
    """Test tool use ID generation 测试工具使用 ID 生成"""
    id1 = generate_tool_use_id()
    id2 = generate_tool_use_id()
    
    assert id1.startswith("toolu_")
    assert id2.startswith("toolu_")
    assert id1 != id2  # Should be unique 应该是唯一的
    assert len(id1) == 30  # toolu_ + 24 chars


def test_generate_xml_tool_instructions():
    """Test XML tool instructions generation 测试 XML 工具指令生成"""
    tools = [
        AnthropicToolDefinition(
            name="read_file",
            description="Read a file from disk",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
        )
    ]
    
    instructions = generate_xml_tool_instructions(tools)
    
    assert "# TOOL CALLING FORMAT" in instructions
    assert "<tool_code" in instructions
    assert "read_file" in instructions
    assert "Read a file from disk" in instructions


def test_generate_xml_tool_instructions_empty():
    """Test XML instructions with empty tools 测试空工具的 XML 指令"""
    instructions = generate_xml_tool_instructions([])
    assert instructions == ""


def test_has_xml_tool_instructions():
    """Test XML tool instructions detection 测试 XML 工具指令检测"""
    with_xml = "# TOOL CALLING FORMAT\n<tool_code name='test'>"
    without_xml = "Normal system prompt"
    
    assert has_xml_tool_instructions(with_xml) is True
    assert has_xml_tool_instructions(without_xml) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
