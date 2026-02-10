"""XML tool prompt generation XML 工具提示生成

Generate XML-based tool instructions for models without native function calling
为不支持原生函数调用的模型生成基于 XML 的工具指令
"""

import json
import html
from typing import Any

from ..models.anthropic import AnthropicToolDefinition


def _escape_xml(text: str) -> str:
    """Escape special XML characters 转义特殊 XML 字符
    
    Args:
        text: Text to escape 要转义的文本
        
    Returns:
        Escaped text 转义后的文本
    """
    return html.escape(text)


def generate_xml_tool_instructions(tools: list[AnthropicToolDefinition]) -> str:
    """Generate XML tool instructions to inject into system prompt
    生成要注入系统提示的 XML 工具指令
    
    This enables models without native function calling to use tools via XML output
    这使不支持原生函数调用的模型能够通过 XML 输出使用工具
    
    Args:
        tools: Tool definitions 工具定义列表
        
    Returns:
        XML instructions string XML 指令字符串
    """
    if not tools:
        return ""
    
    # Format tool definitions 格式化工具定义
    tool_defs = []
    for tool in tools:
        schema_json = json.dumps(tool.input_schema, indent=2, ensure_ascii=False)
        tool_defs.append(f"- **{tool.name}**: {_escape_xml(tool.description)}\n  Parameters: {schema_json}")
    
    tools_list = "\n\n".join(tool_defs)
    
    return f"""
# TOOL CALLING FORMAT

You are required to use tools to fetch information or perform actions.
To invoke a tool, you MUST use the following EXACT XML format.
ANY deviation from this format will cause the tool call to fail.

<tool_code name="TOOL_NAME">
{{"argument_name": "value"}}
</tool_code>

## CRITICAL EXECUTION RULES:
1. **NO Markdown**: Do NOT wrap the XML in ```xml or ``` code blocks. Output the raw XML tags directly.
2. **Valid JSON**: The content between the tags MUST be valid, parseable JSON.
   - Use double quotes for keys and string values.
   - No trailing commas.
   - No comments using // or /*.
3. **Exact Name Match**: The `name` attribute MUST match a tool name from the "Available Tools" list exactly (case-sensitive).
4. **No Nested Content**: The JSON parameters must be the direct child of `tool_code`. Do not nest another `tool` or `function` tag inside.
5. **Thinking**: If you need to think or explain your reasoning, do so in text BEFORE the `<tool_code>` block. Do NOT put thoughts inside the tool code.
6. **Multiple Tools**: You may call multiple tools in sequence by outputting multiple `<tool_code>` blocks.
7. **Tool Outputs**: Tool results will be provided to you in the following format:
<tool_output>
{{result_json_or_text}}
</tool_output>

## EXAMPLE (Correct):
Thinking: I need to read the file.
<tool_code name="Read">
{{"file_path": "src/utils.py"}}
</tool_code>

## EXAMPLES (Incorrect - DO NOT USE):
Wrapped in code blocks:
```xml
<tool_code name="Read">...</tool_code>
```

Nested tags:
<tool_code><tool name="Read">...</tool></tool_code>

Invalid JSON (keys not quoted):
<tool_code name="Read">
{{file_path: "src/utils.py"}}
</tool_code>

## Available Tools:

{tools_list}
"""


def has_xml_tool_instructions(system_prompt: str) -> bool:
    """Check if system prompt already contains XML tool instructions
    检查系统提示是否已包含 XML 工具指令
    
    Args:
        system_prompt: System prompt 系统提示
        
    Returns:
        True if contains XML instructions 如果包含 XML 指令则为 True
    """
    return "# TOOL CALLING FORMAT" in system_prompt and "<tool_code" in system_prompt
