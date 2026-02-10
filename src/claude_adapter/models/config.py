"""Configuration models 配置模型

Pydantic models for adapter configuration
适配器配置的 Pydantic 模型
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


# Provider names type 提供商名称类型
ProviderName = Literal[
    "nvidia",
    "ollama",
    "lmstudio",
    "kimi",
    "deepseek",
    "glm",
    "minimax",
    "custom",
]


class ModelConfig(BaseModel):
    """Model configuration 模型配置
    
    Maps Claude's model tiers to actual model names
    将 Claude 的模型层级映射到实际模型名称
    
    Attributes:
        opus: Complex reasoning model 复杂推理模型
        sonnet: Balanced model 平衡模型
        haiku: Fast model 快速模型
    """

    opus: str = Field(..., description="Model name for Opus tier Opus 层级的模型名称")
    sonnet: str = Field(..., description="Model name for Sonnet tier Sonnet 层级的模型名称")
    haiku: str = Field(..., description="Model name for Haiku tier Haiku 层级的模型名称")


class ProviderPreset(BaseModel):
    """Provider preset configuration 提供商预设配置
    
    Default configuration values for each provider
    每个提供商的默认配置值
    
    Attributes:
        name: Provider name 提供商名称
        label: Display label CLI 显示标签
        base_url: Default API base URL 默认 API 基础 URL
        api_key_required: Whether API key is required 是否需要 API 密钥
        api_key_placeholder: Placeholder for API key input API 密钥输入占位符
        default_models: Default model configuration 默认模型配置
        default_tool_format: Default tool calling format 默认工具调用格式
        description: Provider description 提供商描述
        max_context_window: Maximum context window size 最大上下文窗口大小
    """

    name: ProviderName
    label: str
    base_url: str
    api_key_required: bool
    api_key_placeholder: str
    default_models: ModelConfig
    default_tool_format: Literal["native", "xml"]
    description: str
    max_context_window: Optional[int] = None


class AdapterConfig(BaseModel):
    """Adapter configuration 适配器配置
    
    Complete configuration for a single provider
    单个提供商的完整配置
    
    Attributes:
        provider: Provider name 提供商名称
        base_url: API base URL API 基础 URL
        api_key: API key API 密钥
        models: Model configuration 模型配置
        tool_format: Tool calling format 工具调用格式
        port: Server port 服务器端口
        max_context_window: Maximum context window 最大上下文窗口
    """

    provider: ProviderName
    base_url: str
    api_key: str
    models: ModelConfig
    tool_format: Literal["native", "xml"] = "native"
    port: Optional[int] = 3080
    max_context_window: Optional[int] = None


class GlobalSettings(BaseModel):
    """Global settings 全局设置
    
    Tracks which provider is currently active
    跟踪当前激活的提供商
    
    Attributes:
        active_provider: Currently active provider (None = not set) 当前激活的提供商（None 表示未设置）
        last_used: Last usage timestamp 最后使用时间戳
    """

    active_provider: Optional[ProviderName] = None
    last_used: str  # ISO 8601 timestamp


class ClaudeSettings(BaseModel):
    """Claude Code settings Claude Code 设置
    
    Settings stored in ~/.claude/settings.json
    存储在 ~/.claude/settings.json 的设置
    
    Attributes:
        env: Environment variables 环境变量
    """

    env: Optional[dict[str, str]] = None

    class Config:
        extra = "allow"  # Allow extra fields 允许额外字段


class ClaudeJson(BaseModel):
    """Claude JSON configuration Claude JSON 配置
    
    Configuration stored in ~/.claude.json
    存储在 ~/.claude.json 的配置
    
    Attributes:
        has_completed_onboarding: Whether onboarding is complete 是否完成入职引导
    """

    has_completed_onboarding: Optional[bool] = None

    class Config:
        extra = "allow"  # Allow extra fields 允许额外字段
