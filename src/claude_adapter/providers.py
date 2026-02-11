"""Provider presets 提供商预设

Default configurations for supported providers
支持的提供商的默认配置
"""

from typing import Literal

from .models.config import ProviderPreset, ProviderName, ModelConfig

# Provider category type 提供商分类类型
ProviderCategory = Literal["free", "paid", "custom"]

# Paid provider names for direct Anthropic configuration
# 付费提供商名称（直接配置 Anthropic，无需启动 HTTP 服务器）
PAID_PROVIDER_NAMES: tuple[Literal["kimi", "deepseek", "glm", "minimax"], ...] = (
    "kimi",
    "deepseek",
    "glm",
    "minimax",
)

# ─── Category definitions 分类定义 ───
PROVIDER_CATEGORIES: dict[ProviderCategory, list[ProviderName]] = {
    "free": ["nvidia", "ollama", "lmstudio"],
    "paid": ["kimi", "deepseek", "glm", "minimax"],
    "custom": ["custom"],
}

# ─── Category display labels 分类显示标签 ───
CATEGORY_LABELS: dict[ProviderCategory, str] = {
    "free": "Free (免费)",
    "paid": "Paid (付费)",
    "custom": "Custom (自定义)",
}

# ─── Setup guidance per provider 每个提供商的设置引导 ───
PROVIDER_GUIDANCE: dict[ProviderName, list[str]] = {
    "nvidia": [
        "NVIDIA NIM 使用步骤:",
        "   1. 访问 https://build.nvidia.com/ 注册账号",
        "   2. 在控制台获取 API Key (格式: nvapi-xxxx)",
        "   3. 选择模型（推荐 minimaxai/minimax-m2.1）",
        "   4. 配置完成后即可使用",
    ],
    "ollama": [
        "Ollama 使用步骤:",
        "   1. 安装 Ollama: https://ollama.com/download",
        "   2. 启动服务:",
        "      $ ollama serve",
        "   3. 拉取本地模型:",
        "      $ ollama pull qwen2.5-coder:32b          (本地模型)",
        "      $ ollama pull kimi-k2.5:cloud             (云端模型)",
        "   4. 查看已有模型:",
        "      $ ollama list",
        "",
        "   Ollama 支持本地模型（ollama pull name）和云端模型",
        "   （ollama pull name:cloud），确保 ollama serve 已启动",
    ],
    "lmstudio": [
        "LM Studio 使用步骤:",
        "   1. 下载 LM Studio: https://lmstudio.ai/",
        "   2. 搜索并下载模型:",
        "      $ lms get <model-name>",
        "   3. 加载模型:",
        "      $ lms load <model-name>",
        "   4. 启动服务:",
        "      $ lms server start",
        "",
        "   LM Studio 仅支持本地模型，需先用 lms get 下载",
        "   若模型实际上下文为 4096，配置时请将「上下文窗口」设为 4096，避免 n_keep>=n_ctx 错误",
    ],
    "kimi": [
        "Kimi (月之暗面) Anthropic 直接配置:",
        "   1. 访问 https://platform.moonshot.cn/console/api-keys",
        "   2. 注册账号并创建 API Key (格式: sk-xxxx)",
        "   3. 推荐模型: kimi-k2.5",
        "   4. 配置完成后直接使用 Claude Code，无需启动 HTTP 服务器",
    ],
    "deepseek": [
        "DeepSeek Anthropic 直接配置:",
        "   1. 访问 https://platform.deepseek.com/api_keys",
        "   2. 注册账号并创建 API Key (格式: sk-xxxx)",
        "   3. 推荐模型: deepseek-chat",
        "   4. 配置完成后直接使用 Claude Code，无需启动 HTTP 服务器",
    ],
    "glm": [
        "Z.ai (智谱 AI) Anthropic 直接配置:",
        "   1. 访问 https://bigmodel.cn/usercenter/proj-mgmt/apikeys",
        "   2. 注册账号并创建 API Key (格式: xxxx.xxxx)",
        "   3. 推荐模型: glm-4.7",
        "   4. 配置完成后直接使用 Claude Code，无需启动 HTTP 服务器",
    ],
    "minimax": [
        "MiniMax Anthropic 直接配置:",
        "   1. 访问 https://platform.minimaxi.com/user-center/basic-information/interface-key",
        "   2. 注册账号并创建 API Key (格式: eyxxxx)",
        "   3. 推荐模型: MiniMax-M2.1",
        "   4. 配置完成后直接使用 Claude Code，无需启动 HTTP 服务器",
    ],
    "custom": [
        "自定义 OpenAI-compatible 接口:",
        "   1. 准备好任意兼容 OpenAI API 的服务端点",
        "   2. 输入 Base URL (如 https://api.openai.com/v1)",
        "   3. 输入 API Key",
        "   4. 输入要使用的模型名称",
    ],
}


# ─── All supported provider presets 所有支持的提供商预设 ───
PROVIDER_PRESETS: dict[ProviderName, ProviderPreset] = {
    "nvidia": ProviderPreset(
        name="nvidia",
        label="NVIDIA NIM",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key_required=True,
        api_key_placeholder="nvapi-xxxx",
        default_models=ModelConfig(
            opus="minimaxai/minimax-m2.1",
            sonnet="minimaxai/minimax-m2.1",
            haiku="minimaxai/minimax-m2.1",
        ),
        default_tool_format="native",
        description="NVIDIA NIM API (https://build.nvidia.com/)",
    ),
    "ollama": ProviderPreset(
        name="ollama",
        label="Ollama",
        base_url="http://localhost:11434/v1",
        api_key_required=False,
        api_key_placeholder="ollama",
        default_models=ModelConfig(
            opus="kimi-k2.5:cloud",
            sonnet="kimi-k2.5:cloud",
            haiku="kimi-k2.5:cloud",
        ),
        default_tool_format="native",
        description="Ollama localhost:11434 (https://ollama.com/)",
        max_context_window=8192,
    ),
    "lmstudio": ProviderPreset(
        name="lmstudio",
        label="LM Studio",
        base_url="http://localhost:1234/v1",
        api_key_required=False,
        api_key_placeholder="lm-studio",
        default_models=ModelConfig(
            opus="zai-org/glm-4.7-flash",
            sonnet="zai-org/glm-4.7-flash",
            haiku="zai-org/glm-4.7-flash",
        ),
        default_tool_format="native",
        description="LM Studio localhost:1234 (https://lmstudio.ai/)",
        max_context_window=131072,
    ),
    "kimi": ProviderPreset(
        name="kimi",
        label="Kimi (Moonshot)",
        base_url="https://api.moonshot.cn/anthropic",
        api_key_required=True,
        api_key_placeholder="sk-xxxx",
        default_models=ModelConfig(
            opus="kimi-k2.5",
            sonnet="kimi-k2.5",
            haiku="kimi-k2.5",
        ),
        default_tool_format="native",
        description="Kimi API (https://platform.moonshot.cn/console/api-keys)",
    ),
    "deepseek": ProviderPreset(
        name="deepseek",
        label="DeepSeek",
        base_url="https://api.deepseek.com/anthropic",
        api_key_required=True,
        api_key_placeholder="sk-xxxx",
        default_models=ModelConfig(
            opus="deepseek-chat",
            sonnet="deepseek-chat",
            haiku="deepseek-chat",
        ),
        default_tool_format="native",
        description="DeepSeek API (https://platform.deepseek.com/api_keys)",
    ),
    "glm": ProviderPreset(
        name="glm",
        label="Z.ai",
        base_url="https://api.z.ai/api/anthropic",
        api_key_required=True,
        api_key_placeholder="xxxx.xxxx",
        default_models=ModelConfig(
            opus="glm-4.7",
            sonnet="glm-4.7",
            haiku="glm-4.7",
        ),
        default_tool_format="native",
        description="Z.ai API (https://bigmodel.cn/usercenter/proj-mgmt/apikeys)",
    ),
    "minimax": ProviderPreset(
        name="minimax",
        label="MiniMax",
        base_url="https://api.minimaxi.com/anthropic",
        api_key_required=True,
        api_key_placeholder="eyxxxx",
        default_models=ModelConfig(
            opus="MiniMax-M2.1",
            sonnet="MiniMax-M2.1",
            haiku="MiniMax-M2.1",
        ),
        default_tool_format="native",
        description="MiniMax API (https://platform.minimaxi.com/)",
    ),
    "custom": ProviderPreset(
        name="custom",
        label="Custom OpenAI-compatible",
        base_url="https://api.openai.com/v1",
        api_key_required=True,
        api_key_placeholder="sk-xxxx",
        default_models=ModelConfig(
            opus="gpt-4o",
            sonnet="gpt-4o",
            haiku="gpt-4o-mini",
        ),
        default_tool_format="native",
        description="Custom OpenAI-compatible endpoint",
    ),
}


def get_provider_preset(name: ProviderName) -> ProviderPreset:
    """Get a provider preset by name
    根据名称获取提供商预设

    Args:
        name: Provider name 提供商名称

    Returns:
        Provider preset 提供商预设

    Raises:
        KeyError: If provider not found 如果提供商未找到
    """
    return PROVIDER_PRESETS[name]


def get_provider_names() -> list[ProviderName]:
    """Get all provider names
    获取所有提供商名称

    Returns:
        List of provider names 提供商名称列表
    """
    return list(PROVIDER_PRESETS.keys())


def get_providers_by_category(category: ProviderCategory) -> list[ProviderPreset]:
    """Get providers by category
    按分类获取提供商

    Args:
        category: Provider category (free/paid/custom) 提供商分类

    Returns:
        List of provider presets 提供商预设列表
    """
    names = PROVIDER_CATEGORIES.get(category, [])
    return [PROVIDER_PRESETS[n] for n in names if n in PROVIDER_PRESETS]


def get_provider_guidance(name: ProviderName) -> list[str]:
    """Get setup guidance for a provider
    获取提供商的设置引导

    Args:
        name: Provider name 提供商名称

    Returns:
        List of guidance strings 引导文本列表
    """
    return PROVIDER_GUIDANCE.get(name, [])
