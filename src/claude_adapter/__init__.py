"""Claude Adapter Python

Python adapter to use OpenAI-compatible APIs with Claude Code
使用 OpenAI 兼容 API 与 Claude Code 的 Python 适配器

This package provides a local HTTP server that translates Anthropic Messages API
requests to OpenAI Chat Completions format.
这个包提供了一个本地 HTTP 服务器，将 Anthropic Messages API 请求转换为 OpenAI Chat Completions 格式。
"""

from .models.config import (
    ProviderName,
    ModelConfig,
    ProviderPreset,
    AdapterConfig,
)
from .providers import PROVIDER_PRESETS, get_provider_preset, get_providers_by_category
from .utils.config import (
    load_provider_config,
    save_provider_config,
    get_active_provider,
    set_active_provider,
)
from .utils.metadata import CURRENT_VERSION

__version__ = CURRENT_VERSION

__all__ = [
    "__version__",
    # Config
    "ProviderName",
    "ModelConfig",
    "ProviderPreset",
    "AdapterConfig",
    # Providers
    "PROVIDER_PRESETS",
    "get_provider_preset",
    "get_providers_by_category",
    # Utils
    "load_provider_config",
    "save_provider_config",
    "get_active_provider",
    "set_active_provider",
]
