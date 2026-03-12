"""CLI custom provider regression tests 自定义提供商回归测试"""

from __future__ import annotations

import importlib


def test_configure_custom_does_not_pass_none_default_to_password(monkeypatch):
    cli = importlib.import_module("claude_adapter.cli")

    class _FakePrompt:
        def __init__(self, value):
            self._value = value

        def ask(self):
            return self._value

    class _FakeQuestionary:
        @staticmethod
        def password(message, default=None):
            # Regression assertion: default must be string, not None
            assert default is not None
            assert isinstance(default, str)
            return _FakePrompt("test-key")

        @staticmethod
        def text(message, default=None):
            if "Base URL" in message:
                return _FakePrompt("https://example.com/v1")
            if "Server port" in message:
                return _FakePrompt("3080")
            if "Claude Opus" in message:
                return _FakePrompt("gpt-4o")
            if "Claude Sonnet" in message:
                return _FakePrompt("gpt-4o")
            if "Claude Haiku" in message:
                return _FakePrompt("gpt-4o-mini")
            if "Max context window" in message:
                return _FakePrompt("")
            return _FakePrompt(default or "")

        @staticmethod
        def select(message, choices, default=None):
            # Select native mode for tool format
            return _FakePrompt("native")

    monkeypatch.setattr(cli, "questionary", _FakeQuestionary)
    monkeypatch.setattr(cli, "save_provider_config", lambda *_: None)
    monkeypatch.setattr(cli, "set_active_provider", lambda *_: None)
    monkeypatch.setattr(cli, "load_provider_config", lambda *_: None)

    preset = cli.get_provider_preset("custom")
    config = cli._configure_free_provider("custom", preset, is_local=False)

    assert config is not None
    assert config.provider == "custom"
    assert config.api_key == "test-key"
