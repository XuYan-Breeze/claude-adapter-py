"""Validation tests 请求验证测试"""

from claude_adapter.utils.validation import validate_anthropic_request


def _base_body():
    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": "hello"}],
    }


def test_validation_passes_for_minimal_valid_request():
    result = validate_anthropic_request(_base_body())
    assert result.valid is True
    assert result.errors == []


def test_validation_rejects_invalid_tool_choice_without_tools():
    body = _base_body()
    body["tool_choice"] = "auto"
    result = validate_anthropic_request(body)
    assert result.valid is False
    assert any(err.field == "tool_choice" for err in result.errors)


def test_validation_rejects_invalid_tools_schema_type():
    body = _base_body()
    body["tools"] = [
        {
            "name": "read_file",
            "description": "Read file",
            "input_schema": {"type": "array"},
        }
    ]
    result = validate_anthropic_request(body)
    assert result.valid is False
    assert any(err.field.endswith("input_schema.type") for err in result.errors)


def test_validation_rejects_user_tool_use_block():
    body = _base_body()
    body["messages"] = [
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "read_file",
                    "input": {"path": "a.txt"},
                }
            ],
        }
    ]
    result = validate_anthropic_request(body)
    assert result.valid is False
    assert any("cannot contain \"tool_use\"" in err.message for err in result.errors)


def test_validation_rejects_assistant_tool_result_block():
    body = _base_body()
    body["messages"] = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_123",
                    "content": "ok",
                }
            ],
        }
    ]
    result = validate_anthropic_request(body)
    assert result.valid is False
    assert any("cannot contain \"tool_result\"" in err.message for err in result.errors)


def test_validation_accepts_valid_tools_and_tool_choice():
    body = _base_body()
    body["tools"] = [
        {
            "name": "read_file",
            "description": "Read file",
            "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
        }
    ]
    body["tool_choice"] = {"type": "tool", "name": "read_file"}
    result = validate_anthropic_request(body)
    assert result.valid is True


def test_validation_rejects_invalid_top_k_and_stop_sequences():
    body = _base_body()
    body["top_k"] = 0
    body["stop_sequences"] = ["ok", 1]
    result = validate_anthropic_request(body)
    assert result.valid is False
    assert any(err.field == "top_k" for err in result.errors)
    assert any(err.field == "stop_sequences" for err in result.errors)

