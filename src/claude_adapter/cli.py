"""Command-line interface 命令行界面

CLI for Claude Adapter using Typer
使用 Typer 的 Claude 适配器命令行界面

Paid providers (kimi/deepseek/glm/minimax):
  - Direct Anthropic API, no HTTP server needed
  - Configure API Key only
  - Write to ~/.claude/settings.json
  - Auto-cache to ~/.claude-adapter/providers/

Free providers (nvidia/ollama/lmstudio):
  - Requires HTTP server proxy
  - Full configuration (Base URL, port, models)
  - Auto-cache to ~/.claude-adapter/providers/
"""

import asyncio
import sys
from typing import Optional, Union

import questionary
import typer
from rich.table import Table

from .models.config import AdapterConfig, ModelConfig, ProviderName, ProviderPreset
from .providers import (
    PROVIDER_PRESETS,
    CATEGORY_LABELS,
    get_provider_preset,
    get_providers_by_category,
    get_provider_guidance,
    PAID_PROVIDER_NAMES,
)
from .utils.config import (
    get_active_provider,
    load_provider_config,
    save_provider_config,
    set_active_provider,
    list_saved_providers,
    delete_provider_config,
    update_claude_json,
    update_claude_settings,
    update_claude_settings_for_paid_provider,
    load_paid_provider_cache,
    save_paid_provider_to_cache,
)
from .utils.update import get_cached_update_info
from .utils import ui
from .server import run_server

# ─── Create Typer app ───
app = typer.Typer(
    name="claude-adapter-py",
    help="Claude Adapter - Use OpenAI-compatible APIs with Claude Code",
    add_completion=False,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


# Sentinel: go back to previous step 返回上一步
BACK = "back"
EXIT = "exit"


def _is_paid_provider(provider_name: str) -> bool:
    """Check if provider is a paid provider
    检查是否是付费提供商
    """
    return provider_name in PAID_PROVIDER_NAMES


# ═══════════════════════════════════════════════════════════
#  Provider selection  选择提供商
# ═══════════════════════════════════════════════════════════

def _select_provider() -> Union[Optional[ProviderName], str]:
    """Interactive provider selection with category grouping
    交互式提供商选择，带分类分组

    Returns:
        Provider name, or BACK to re-select category, or None to exit
        提供商名称，或 BACK 返回重选分类，或 None 退出
    """
    ui.header("Select Provider 选择提供商")

    # ── Category selection 分类选择 ──
    category_choices = [
        questionary.Choice(
            f"{CATEGORY_LABELS['free']}   NVIDIA, Ollama, LM Studio (需要启动 HTTP 服务器)",
            value="free",
        ),
        questionary.Choice(
            f"{CATEGORY_LABELS['paid']}   Kimi, DeepSeek, GLM, MiniMax (直接 Anthropic API，无需服务器)",
            value="paid",
        ),
        questionary.Choice(
            f"{CATEGORY_LABELS['custom']} OpenAI-compatible endpoint",
            value="custom",
        ),
        questionary.Choice("Go back  返回重新选择", value=BACK),
        questionary.Choice("Exit  退出", value=EXIT),
    ]

    category = questionary.select(
        "Choose provider type 选择提供商类型:",
        choices=category_choices,
    ).ask()

    if not category or category == EXIT or category == BACK:
        return None

    # ── Provider selection within category 分类内选择提供商 ──
    providers = get_providers_by_category(category)

    if len(providers) == 1:
        return providers[0].name

    provider_choices = [
        questionary.Choice(
            f"{p.label.ljust(22)} {p.description}",
            value=p.name,
        )
        for p in providers
    ]
    provider_choices.append(questionary.Choice("Go back  返回重新选择", value=BACK))
    provider_choices.append(questionary.Choice("Exit  退出", value=EXIT))

    selected = questionary.select(
        "Choose provider 选择提供商:",
        choices=provider_choices,
    ).ask()

    if not selected or selected == EXIT:
        return None
    if selected == BACK:
        return BACK
    return selected  # type: ignore


# ═══════════════════════════════════════════════════════════
#  Paid provider configuration  付费提供商配置
# ═══════════════════════════════════════════════════════════

def _configure_paid_provider(provider_name: ProviderName, preset: ProviderPreset) -> bool:
    """Configure a paid provider (direct Anthropic API, no HTTP server)
    配置付费提供商（直接 Anthropic API，无需 HTTP 服务器）

    Returns:
        True if configured successfully, False if cancelled
    """
    ui.header(f"Configure {preset.label}")

    # Check for cached config 检查缓存配置
    cached = load_paid_provider_cache(provider_name)
    if cached:
        print()
        ui.info("Found cached configuration 发现已缓存的配置")
        choices = [
            questionary.Choice("Use cached API Key  使用已缓存的 API Key", value="use"),
            questionary.Choice("Reconfigure  重新配置", value="reconfig"),
            questionary.Choice("Go back  返回", value=BACK),
            questionary.Choice("Exit  退出", value=EXIT),
        ]
        action = questionary.select(
            f"{preset.label} - 已缓存配置",
            choices=choices,
        ).ask()

        if action == "use":
            api_key = cached["api_key"]
        elif action == "reconfig":
            api_key = None
        elif action == BACK:
            return False
        else:
            sys.exit(0)
    else:
        api_key = None

    # Get API Key if not using cache 如果不使用缓存，获取 API Key
    if api_key is None:
        print()
        api_key = questionary.password(
            f"Enter {preset.label} API Key ({preset.api_key_placeholder}):",
        ).ask()

        if not api_key or not api_key.strip():
            ui.warning("API Key is required")
            return False

    # Configure and write to ~/.claude/settings.json
    try:
        update_claude_json()
        update_claude_settings_for_paid_provider(
            provider_name=provider_name,
            api_key=api_key.strip(),
            model_name=preset.default_models.opus,
            base_url=preset.base_url,
        )
    except Exception as e:
        ui.error("Failed to update Claude settings", str(e))
        return False

    # Save to cache 保存到缓存
    try:
        save_paid_provider_to_cache(
            provider_name=provider_name,
            api_key=api_key.strip(),
            opus_model=preset.default_models.opus,
            sonnet_model=preset.default_models.sonnet,
            haiku_model=preset.default_models.haiku,
            base_url=preset.base_url,
        )
    except Exception as e:
        ui.warning(f"Failed to cache config: {str(e)}")

    print()
    ui.success(f"{preset.label} configured successfully!")
    ui.info("无需启动 HTTP 服务器，直接使用 Claude Code 即可")
    print()
    ui.hint(f"API Key 已保存到 ~/.claude/settings.json")
    print()

    return True


# ═══════════════════════════════════════════════════════════
#  Free provider configuration  免费提供商配置
# ═══════════════════════════════════════════════════════════

def _action_has_config_free(preset: ProviderPreset) -> Optional[str]:
    """When a saved config exists (free provider), choose action
    已有存储配置时选择操作（免费提供商）

    Returns:
        "use" | "reconfigure" | "back" | "exit" | None
    """
    choices = [
        questionary.Choice("Use saved config  使用已缓存的配置", value="use"),
        questionary.Choice("Reconfigure  重新配置参数", value="reconfigure"),
        questionary.Choice("Go back  返回重新选择", value=BACK),
        questionary.Choice("Exit  退出", value=EXIT),
    ]

    return questionary.select(
        f"{preset.label} - 已有缓存配置",
        choices=choices,
    ).ask()


def _action_no_config_free(preset: ProviderPreset) -> Optional[str]:
    """When no saved config (free provider), choose action
    无存储配置时选择操作（免费提供商）

    Returns:
        "configure" | "back" | "exit" | None
    """
    choices = [
        questionary.Choice("Configure  配置参数并启动", value="configure"),
        questionary.Choice("Go back  返回重新选择", value=BACK),
        questionary.Choice("Exit  退出", value=EXIT),
    ]

    return questionary.select(
        f"{preset.label} - 尚未配置",
        choices=choices,
    ).ask()


def _configure_free_provider(
    provider_name: ProviderName,
    preset: ProviderPreset,
    is_local: bool = False,
) -> Optional[AdapterConfig]:
    """Configure a free provider (requires HTTP server)
    配置免费提供商（需要 HTTP 服务器）

    Returns:
        AdapterConfig when done, None when user chose Go back
    """
    ui.header(f"Configure {preset.label}")

    existing = load_provider_config(provider_name)

    # ── API Key (not needed for local services) ──
    if is_local:
        api_key = ""
    elif preset.api_key_required:
        default_key = existing.api_key if existing else ""
        api_key_input = questionary.password(
            f"API Key ({preset.api_key_placeholder}):",
            default=default_key if default_key else None,
        ).ask()
        api_key = api_key_input or preset.api_key_placeholder
    else:
        api_key = ""

    # ── Base URL ──
    if is_local:
        ui.info(f"Server URL: {preset.base_url}")
        base_url = preset.base_url
    else:
        default_url = existing.base_url if existing else preset.base_url
        base_url = questionary.text(
            "Base URL:",
            default=default_url,
        ).ask()
        if not base_url:
            base_url = preset.base_url

    # ── Server port ──
    default_port = str(existing.port) if existing and existing.port else "3080"
    port_str = questionary.text(
        "Server port 服务端口:",
        default=default_port,
    ).ask()
    port = int(port_str) if port_str and port_str.isdigit() else 3080

    # ── Model mappings ──
    ui.info("Model mappings 模型映射, press Enter to use defaults 回车使用默认值:")

    def_opus = existing.models.opus if existing else preset.default_models.opus
    def_sonnet = existing.models.sonnet if existing else preset.default_models.sonnet
    def_haiku = existing.models.haiku if existing else preset.default_models.haiku

    opus_model = questionary.text(
        "  Claude Opus   -> ",
        default=def_opus,
    ).ask() or def_opus

    sonnet_model = questionary.text(
        "  Claude Sonnet -> ",
        default=def_sonnet,
    ).ask() or def_sonnet

    haiku_model = questionary.text(
        "  Claude Haiku  -> ",
        default=def_haiku,
    ).ask() or def_haiku

    # ── Tool format ──
    native_choice = questionary.Choice("native  function calling", value="native")
    xml_choice = questionary.Choice("xml  prompt-based, for local models", value="xml")
    default_fmt = native_choice if preset.default_tool_format == "native" else xml_choice

    tool_choices = [native_choice, xml_choice]
    tool_choices.append(questionary.Choice("Go back  返回重新选择", value=BACK))
    tool_choices.append(questionary.Choice("Exit  退出", value=EXIT))

    tool_format = questionary.select(
        "Tool calling format 工具调用格式:",
        choices=tool_choices,
        default=default_fmt,
    ).ask()

    if tool_format == BACK:
        return None
    if tool_format == EXIT or not tool_format:
        raise typer.Exit(0)

    # ── Max context window ──
    is_lmstudio = provider_name == "lmstudio"
    default_ctx = ""
    if existing and existing.max_context_window is not None:
        default_ctx = str(existing.max_context_window)
    elif preset.max_context_window:
        default_ctx = str(preset.max_context_window) if not is_lmstudio else "4096"
    if is_lmstudio and not default_ctx:
        default_ctx = "4096"

    ctx_str = questionary.text(
        "Max context window 最大上下文长度 (LM Studio 必填 required):"
        if is_lmstudio
        else "Max context window 最大上下文长度 (optional 可选, Enter=default):",
        default=default_ctx,
    ).ask()

    max_context_window: Optional[int] = None
    if ctx_str and ctx_str.strip():
        try:
            n = int(ctx_str.strip())
            max_context_window = n if n > 0 else (4096 if is_lmstudio else preset.max_context_window)
        except ValueError:
            max_context_window = 4096 if is_lmstudio else preset.max_context_window
    else:
        max_context_window = 4096 if is_lmstudio else preset.max_context_window

    # ── Build & save ──
    config = AdapterConfig(
        provider=provider_name,
        api_key=api_key,
        base_url=base_url,
        port=port,
        models=ModelConfig(
            opus=opus_model,
            sonnet=sonnet_model,
            haiku=haiku_model,
        ),
        tool_format=tool_format,  # type: ignore
        max_context_window=max_context_window,
    )

    save_provider_config(config)
    set_active_provider(provider_name)

    ui.success(f"Saved {preset.label} configuration")
    return config


# ═══════════════════════════════════════════════════════════
#  Display config & start server  显示配置 & 启动服务器
# ═══════════════════════════════════════════════════════════

def _display_config(config: AdapterConfig, preset: ProviderPreset, port: Optional[int]) -> None:
    """Display current configuration summary 显示当前配置摘要"""
    print()
    rows: list[tuple[str, str]] = [
        ("Provider", preset.label),
        ("Base URL", config.base_url),
        ("Port", str(port or config.port or 3080)),
        ("Opus", config.models.opus),
        ("Sonnet", config.models.sonnet),
        ("Haiku", config.models.haiku),
        ("Tool Format", config.tool_format),
    ]
    if config.max_context_window is not None:
        rows.append(("Max context window", str(config.max_context_window)))
    ui.table(rows)


def _update_claude_and_start(
    config: AdapterConfig,
    port: Optional[int],
    no_claude_settings: bool,
) -> None:
    """Update Claude settings and start server
    更新 Claude 设置并启动服务器
    """
    if not no_claude_settings:
        try:
            server_port = port or config.port or 3080
            proxy_url = f"http://localhost:{server_port}"

            update_claude_json()
            update_claude_settings(proxy_url, config.models)

            ui.success("Updated Claude settings")
            ui.hint(f'export ANTHROPIC_BASE_URL="{proxy_url}"')
        except Exception as e:
            ui.warning(f"Failed to update Claude settings: {str(e)}")

    print()
    ui.info("Starting server...")

    try:
        asyncio.run(run_server(config, port))
    except KeyboardInterrupt:
        print()
        ui.info("Server stopped")
    except Exception as e:
        ui.error("Server error", e)
        raise typer.Exit(1)


# ═══════════════════════════════════════════════════════════
#  Main CLI callback  主 CLI 回调
# ═══════════════════════════════════════════════════════════

@app.callback()
def main(
    ctx: typer.Context,
    port: Optional[int] = typer.Option(None, "-p", "--port", help="Server port"),
    reconfigure: bool = typer.Option(False, "-r", "--reconfigure", help="Force reconfigure"),
    no_claude_settings: bool = typer.Option(
        False, "--no-claude-settings", help="Skip updating Claude settings"
    ),
) -> None:
    """Start Claude Adapter server"""
    if ctx.invoked_subcommand is not None:
        return

    # ── Banner ──
    ui.banner()

    # ── Check for updates ──
    update_info = get_cached_update_info()
    if update_info and update_info.has_update:
        ui.update_notify(update_info.current, update_info.latest)

    # ══════════════════════════════════════════════════
    #  Main loop  主循环
    # ══════════════════════════════════════════════════

    while True:
        # ── Select provider 选择提供商 ──
        provider_name = _select_provider()
        if provider_name == BACK:
            continue
        if not provider_name:
            ui.warning("No provider selected")
            raise typer.Exit(0)

        provider_name_str = provider_name  # type: ignore
        preset = get_provider_preset(provider_name_str)
        is_paid = _is_paid_provider(provider_name_str)

        if is_paid:
            # ═════ Paid provider (direct Anthropic, no HTTP server) ═════
            cached = load_paid_provider_cache(provider_name_str)

            if cached and not reconfigure:
                # Has cached config 有缓存配置
                choices = [
                    questionary.Choice("Use cached config  使用已缓存的配置", value="use"),
                    questionary.Choice("Reconfigure  重新配置", value="reconfig"),
                    questionary.Choice("Go back  返回", value=BACK),
                    questionary.Choice("Exit  退出", value=EXIT),
                ]
                action = questionary.select(
                    f"{preset.label} - 付费提供商 (直接 Anthropic API)",
                    choices=choices,
                ).ask()

                if action == "use":
                    # Use cached API key 使用缓存的 API Key
                    try:
                        update_claude_json()
                        update_claude_settings_for_paid_provider(
                            provider_name=provider_name_str,
                            api_key=cached["api_key"],
                            model_name=preset.default_models.opus,
                            base_url=cached.get("base_url", preset.base_url),
                        )
                        print()
                        ui.success(f"{preset.label} configured from cache!")
                        ui.info("无需启动 HTTP 服务器，直接使用 Claude Code 即可")
                    except Exception as e:
                        ui.error("Failed to save settings", str(e))
                    raise typer.Exit(0)

                if action == "reconfig":
                    _configure_paid_provider(provider_name_str, preset)
                    raise typer.Exit(0)

                if action == BACK:
                    continue
                raise typer.Exit(0)

            else:
                # No cached config, configure now 无缓存，立即配置
                if _configure_paid_provider(provider_name_str, preset):
                    raise typer.Exit(0)
                continue

        else:
            # ═════ Free provider (requires HTTP server) ═════
            is_local = provider_name_str in ("ollama", "lmstudio")
            existing = load_provider_config(provider_name_str)

            if existing and not reconfigure:
                # Has saved config 已有存储配置
                action = _action_has_config_free(preset)

                if action == "use":
                    set_active_provider(provider_name_str)
                    _display_config(existing, preset, port)
                    _update_claude_and_start(existing, port, no_claude_settings)
                    return

                if action == "reconfigure":
                    guidance = get_provider_guidance(provider_name_str)
                    if guidance:
                        print()
                        for line in guidance:
                            if line == "":
                                print()
                            else:
                                ui.console.print(f"  [dim]{line}[/]")
                        print()
                    config = _configure_free_provider(provider_name_str, preset, is_local)
                    if config is None:
                        continue
                    _display_config(config, preset, port)
                    _update_claude_and_start(config, port, no_claude_settings)
                    return

                if action == BACK:
                    continue
                raise typer.Exit(0)

            else:
                # No saved config 无存储配置
                action = _action_no_config_free(preset)

                if action == "configure":
                    guidance = get_provider_guidance(provider_name_str)
                    if guidance:
                        print()
                        for line in guidance:
                            if line == "":
                                print()
                            else:
                                ui.console.print(f"  [dim]{line}[/]")
                        print()
                    config = _configure_free_provider(provider_name_str, preset, is_local)
                    if config is None:
                        continue
                    _display_config(config, preset, port)
                    _update_claude_and_start(config, port, no_claude_settings)
                    return

                if action == BACK:
                    continue
                raise typer.Exit(0)


# ═══════════════════════════════════════════════════════════
#  Subcommands: ls, rm
# ═══════════════════════════════════════════════════════════

@app.command("ls")
def ls() -> None:
    """List saved provider configurations 列出已保存的提供商配置"""
    saved = list_saved_providers()
    active = get_active_provider()

    if not saved:
        ui.warning("No saved provider configurations")
        ui.hint("Run 'claude-adapter-py' to configure a provider")
        return

    ui.header("Saved Providers")

    tbl = Table(show_header=True, show_edge=False, padding=(0, 2))
    tbl.add_column("Provider", style="bold")
    tbl.add_column("Type", style="cyan")
    tbl.add_column("Base URL")
    tbl.add_column("Models")
    tbl.add_column("Active", justify="center")

    for pname in saved:
        config = load_provider_config(pname)
        preset = get_provider_preset(pname)
        is_paid = _is_paid_provider(pname)
        is_active = "✔" if pname == active else ""

        # Determine type label
        if is_paid:
            type_label = "[Paid] 直接 Anthropic"
        elif pname in ("ollama", "lmstudio"):
            type_label = "[Free] 本地"
        else:
            type_label = "[Free] 云端"

        if config:
            models_str = config.models.opus
            if config.models.sonnet != config.models.opus:
                models_str += f", {config.models.sonnet}"
            if config.models.haiku not in [config.models.opus, config.models.sonnet]:
                models_str += f", {config.models.haiku}"
            tbl.add_row(preset.label, type_label, config.base_url, models_str, is_active)
        else:
            # Paid provider without full config (only has cache)
            cached = load_paid_provider_cache(pname)
            if cached:
                base_url = cached.get("base_url", preset.base_url)
                models = cached.get("default_models", {})
                models_str = models.get("opus", preset.default_models.opus)
                tbl.add_row(preset.label, type_label, base_url, models_str, is_active)

    ui.console.print(tbl)
    print()


@app.command("rm")
def rm(
    provider: str = typer.Argument(..., help="Provider name to remove"),
    force: bool = typer.Option(False, "-f", "--force", help="Skip confirmation"),
) -> None:
    """Remove a saved provider configuration 删除已保存的提供商配置"""
    if provider not in PROVIDER_PRESETS:
        ui.error(f"Unknown provider: {provider}")
        ui.hint(f"Valid providers: {', '.join(PROVIDER_PRESETS.keys())}")
        raise typer.Exit(1)

    provider_name: ProviderName = provider  # type: ignore
    preset = get_provider_preset(provider_name)

    # Check if paid provider (only has cache, no full config)
    is_paid = _is_paid_provider(provider_name)
    config = load_provider_config(provider_name) if not is_paid else None
    cached = load_paid_provider_cache(provider_name) if is_paid else None

    if not config and not cached:
        ui.warning(f"No saved configuration for {provider}")
        return

    if not force:
        choices = [
            questionary.Choice(f"Yes, remove  确认删除 {preset.label} 配置", value="yes"),
            questionary.Choice("Go back  返回重新选择", value=BACK),
            questionary.Choice("Exit  退出", value=EXIT),
        ]
        confirm = questionary.select(
            f"Remove configuration for {preset.label}?",
            choices=choices,
        ).ask()
        if confirm != "yes":
            if confirm == BACK:
                ui.info("Go back")
            else:
                ui.info("Cancelled")
            return

    # Delete config
    if config:
        delete_provider_config(provider_name)

    # Delete cache
    if cached:
        try:
            from .utils.config import PROVIDERS_DIR
            cache_file = PROVIDERS_DIR / f"{provider_name}.json"
            if cache_file.exists():
                cache_file.unlink()
        except Exception:
            pass

    if get_active_provider() == provider_name:
        set_active_provider(None)

    ui.success(f"Removed configuration for {provider}")


# ═══════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════

def cli_main() -> None:
    """Entry point for CLI"""
    try:
        app()
    except KeyboardInterrupt:
        print()
        ui.info("Cancelled")
        sys.exit(0)
    except Exception as e:
        ui.error("Unexpected error", e)
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
