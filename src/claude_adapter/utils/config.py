"""Configuration management 配置管理

Functions for managing provider configurations
管理提供商配置的函数
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models.config import (
    AdapterConfig,
    GlobalSettings,
    ProviderName,
    ModelConfig,
    ClaudeJson,
    ClaudeSettings,
)
from .file_storage import ensure_dir_exists, get_base_dir

# Configuration directories 配置目录
CONFIG_DIR = get_base_dir()
PROVIDERS_DIR = CONFIG_DIR / "providers"
GLOBAL_SETTINGS_FILE = CONFIG_DIR / "settings.json"

# Claude settings paths Claude 设置路径
CLAUDE_JSON_PATH = Path.home() / ".claude.json"
CLAUDE_SETTINGS_DIR = Path.home() / ".claude"
CLAUDE_SETTINGS_PATH = CLAUDE_SETTINGS_DIR / "settings.json"


def _ensure_dirs() -> None:
    """Ensure required directories exist 确保所需目录存在"""
    ensure_dir_exists(CONFIG_DIR)
    ensure_dir_exists(PROVIDERS_DIR)


def _get_provider_config_path(provider: ProviderName) -> Path:
    """Get config file path for a provider 获取提供商的配置文件路径
    
    Args:
        provider: Provider name 提供商名称
        
    Returns:
        Config file path 配置文件路径
    """
    return PROVIDERS_DIR / f"{provider}.json"


# Provider configuration management 提供商配置管理
def load_provider_config(provider: ProviderName) -> Optional[AdapterConfig]:
    """Load configuration for a specific provider 加载特定提供商的配置
    
    Args:
        provider: Provider name 提供商名称
        
    Returns:
        Adapter configuration or None 适配器配置或 None
    """
    config_path = _get_provider_config_path(provider)
    if not config_path.exists():
        return None
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AdapterConfig(**data)
    except Exception:
        return None


def save_provider_config(config: AdapterConfig) -> None:
    """Save configuration for a specific provider 保存特定提供商的配置
    
    Args:
        config: Adapter configuration 适配器配置
    """
    _ensure_dirs()
    config_path = _get_provider_config_path(config.provider)
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)


def provider_config_exists(provider: ProviderName) -> bool:
    """Check if provider configuration exists 检查提供商配置是否存在
    
    Args:
        provider: Provider name 提供商名称
        
    Returns:
        True if exists 如果存在则为 True
    """
    return _get_provider_config_path(provider).exists()


def list_saved_providers() -> list[ProviderName]:
    """List all saved provider configurations 列出所有已保存的提供商配置
    
    Returns:
        List of provider names 提供商名称列表
    """
    _ensure_dirs()
    
    if not PROVIDERS_DIR.exists():
        return []
    
    providers: list[ProviderName] = []
    for file_path in PROVIDERS_DIR.glob("*.json"):
        provider_name = file_path.stem
        # Type checking will ensure only valid provider names
        # 类型检查将确保只有有效的提供商名称
        providers.append(provider_name)  # type: ignore
    
    return providers


def delete_provider_config(provider: ProviderName) -> bool:
    """Delete a provider configuration 删除提供商配置
    
    Args:
        provider: Provider name 提供商名称
        
    Returns:
        True if deleted successfully 如果删除成功则为 True
    """
    config_path = _get_provider_config_path(provider)
    if config_path.exists():
        config_path.unlink()
        return True
    return False


# Global settings management 全局设置管理
def load_global_settings() -> Optional[GlobalSettings]:
    """Load global settings 加载全局设置
    
    Returns:
        Global settings or None 全局设置或 None
    """
    if not GLOBAL_SETTINGS_FILE.exists():
        return None
    
    try:
        with open(GLOBAL_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return GlobalSettings(**data)
    except Exception:
        return None


def save_global_settings(settings: GlobalSettings) -> None:
    """Save global settings 保存全局设置
    
    Args:
        settings: Global settings 全局设置
    """
    _ensure_dirs()
    
    with open(GLOBAL_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings.model_dump(), f, indent=2, ensure_ascii=False)


def set_active_provider(provider: Optional[ProviderName]) -> None:
    """Set the active provider 设置活跃的提供商
    
    Args:
        provider: Provider name or None to clear 提供商名称或 None 以清除
    """
    settings = GlobalSettings(
        active_provider=provider,
        last_used=datetime.now().isoformat(),
    )
    save_global_settings(settings)


def get_active_provider() -> Optional[ProviderName]:
    """Get the currently active provider 获取当前活跃的提供商
    
    Returns:
        Provider name or None 提供商名称或 None
    """
    settings = load_global_settings()
    return settings.active_provider if settings else None


# Claude settings management Claude 设置管理
def update_claude_json() -> None:
    """Update ~/.claude.json to set hasCompletedOnboarding
    更新 ~/.claude.json 设置 hasCompletedOnboarding
    """
    # Load existing or create new 加载现有或创建新的
    claude_json = ClaudeJson()
    if CLAUDE_JSON_PATH.exists():
        try:
            with open(CLAUDE_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            claude_json = ClaudeJson(**data)
        except Exception:
            pass
    
    # Update and save 更新并保存
    claude_json.has_completed_onboarding = True
    
    with open(CLAUDE_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(claude_json.model_dump(exclude_none=True), f, indent=2, ensure_ascii=False)


def update_claude_settings(proxy_url: str, models: ModelConfig) -> None:
    """Update ~/.claude/settings.json with proxy environment variables
    使用代理环境变量更新 ~/.claude/settings.json
    
    Args:
        proxy_url: Proxy server URL 代理服务器 URL
        models: Model configuration 模型配置
    """
    # Ensure directory exists 确保目录存在
    ensure_dir_exists(CLAUDE_SETTINGS_DIR)
    
    # Load existing or create new 加载现有或创建新的
    settings = ClaudeSettings()
    if CLAUDE_SETTINGS_PATH.exists():
        try:
            with open(CLAUDE_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            settings = ClaudeSettings(**data)
        except Exception:
            pass
    
    # Update environment variables 更新环境变量
    env = settings.env or {}
    env.update({
        "ANTHROPIC_BASE_URL": proxy_url,
        "ANTHROPIC_AUTH_TOKEN": "default",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": models.opus,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": models.sonnet,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": models.haiku,
    })
    settings.env = env
    
    # Save 保存
    with open(CLAUDE_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings.model_dump(exclude_none=True), f, indent=2, ensure_ascii=False)


# Utility functions 工具函数
def get_config_dir() -> Path:
    """Get the configuration directory path 获取配置目录路径
    
    Returns:
        Config directory path 配置目录路径
    """
    return CONFIG_DIR


def get_providers_dir() -> Path:
    """Get the providers directory path 获取提供商目录路径

    Returns:
        Providers directory path 提供商目录路径
    """
    return PROVIDERS_DIR


# ─── Paid provider configuration (direct Anthropic format)
# 付费提供商配置（直接 Anthropic 格式，无需 HTTP 服务器）
# ───


def update_claude_settings_for_paid_provider(
    provider_name: str,
    api_key: str,
    model_name: str,
    base_url: str,
) -> None:
    """Update ~/.claude/settings.json with direct Anthropic API for paid providers
    为付费提供商更新 ~/.claude/settings.json（直接 Anthropic API，无需 HTTP 服务器）

    Args:
        provider_name: Provider name (kimi/deepseek/glm/minimax)
        api_key: API key for the provider
        model_name: Model name to use
        base_url: Anthropic API base URL
    """
    ensure_dir_exists(CLAUDE_SETTINGS_DIR)

    # Load existing or create new
    settings = ClaudeSettings()
    if CLAUDE_SETTINGS_PATH.exists():
        try:
            with open(CLAUDE_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            settings = ClaudeSettings(**data)
        except Exception:
            pass

    # Update environment variables - direct Anthropic API, no proxy
    env = settings.env or {}
    env.update({
        "ANTHROPIC_BASE_URL": base_url,
        "ANTHROPIC_AUTH_TOKEN": api_key,
        "ANTHROPIC_DEFAULT_OPUS_MODEL": model_name,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": model_name,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": model_name,
    })
    settings.env = env

    # Save
    with open(CLAUDE_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings.model_dump(exclude_none=True), f, indent=2, ensure_ascii=False)


def load_paid_provider_cache(provider_name: str) -> Optional[dict]:
    """Load cached paid provider configuration
    加载缓存的付费提供商配置

    Args:
        provider_name: Provider name

    Returns:
        Cached config dict or None
    """
    from ..providers import PAID_PROVIDER_NAMES
    if provider_name not in PAID_PROVIDER_NAMES:
        return None

    cache_file = PROVIDERS_DIR / f"{provider_name}.json"
    if not cache_file.exists():
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_paid_provider_to_cache(
    provider_name: str,
    api_key: str,
    opus_model: str,
    sonnet_model: str,
    haiku_model: str,
    base_url: str,
) -> None:
    """Save paid provider to cache file
    将付费提供商保存到缓存文件

    Args:
        provider_name: Provider name
        api_key: API key
        opus_model: Opus model name
        sonnet_model: Sonnet model name
        haiku_model: Haiku model name
        base_url: Anthropic base URL
    """
    from ..providers import get_provider_preset

    _ensure_dirs()
    preset = get_provider_preset(provider_name)  # type: ignore

    config = {
        "provider": provider_name,
        "api_key": api_key,
        "base_url": base_url,
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "default_models": {
            "opus": opus_model,
            "sonnet": sonnet_model,
            "haiku": haiku_model,
        },
        "preset_label": preset.label,
    }

    cache_file = PROVIDERS_DIR / f"{provider_name}.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
