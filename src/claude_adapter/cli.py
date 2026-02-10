"""Command-line interface 命令行界面

CLI for Claude Adapter using Typer
使用 Typer 的 Claude 适配器命令行界面

Execution flow 执行流程:
  1. Show banner 显示横幅
  2. Select provider category  free, paid, custom  选择提供商分类
  3. Select provider within category 在分类中选择提供商
  4. If saved config exists:
     a. Use saved config 使用已存储配置
     b. Reconfigure 重新配置参数
  5. If no saved config:
     a. Configure 配置参数
     b. Go back 返回
  6. Start server 启动服务器
"""

import asyncio
import sys
from typing import Optional

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


# ═══════════════════════════════════════════════════════════
#  Select provider  选择提供商
# ═══════════════════════════════════════════════════════════

def _select_provider() -> Optional[ProviderName]:
    """Interactive provider selection with category grouping
    交互式提供商选择，带分类分组

    Returns:
        Selected provider name, or None if cancelled
        选择的提供商名称，取消则为 None
    """
    ui.header("Select Provider 选择提供商")

    # ── Category selection 分类选择 ──
    category_choices = [
        questionary.Choice(
            f"{CATEGORY_LABELS['free']}   NVIDIA, Ollama, LM Studio",
            value="free",
        ),
        questionary.Choice(
            f"{CATEGORY_LABELS['paid']}   Kimi, DeepSeek, GLM, MiniMax",
            value="paid",
        ),
        questionary.Choice(
            f"{CATEGORY_LABELS['custom']} OpenAI-compatible endpoint",
            value="custom",
        ),
    ]

    category = questionary.select(
        "Choose provider type 选择提供商类型:",
        choices=category_choices,
    ).ask()

    if not category:
        return None

    # ── Provider selection within category 分类内选择提供商 ──
    providers = get_providers_by_category(category)

    if len(providers) == 1:
        # Only one in this category, auto-select
        # 该分类仅一个提供商，自动选择
        return providers[0].name

    provider_choices = [
        questionary.Choice(
            f"{p.label.ljust(22)} {p.description}",
            value=p.name,
        )
        for p in providers
    ]

    selected = questionary.select(
        "Choose provider 选择提供商:",
        choices=provider_choices,
    ).ask()

    return selected  # type: ignore


# ═══════════════════════════════════════════════════════════
#  Action selection  操作选择
# ═══════════════════════════════════════════════════════════

def _action_has_config(preset: ProviderPreset) -> Optional[str]:
    """When a saved config exists, choose action
    已存储配置时选择操作

    Returns:
        "use" | "reconfigure" | None
    """
    choices = [
        questionary.Choice(
            f"▶  Use saved config  使用已存储的 {preset.label} 配置启动",
            value="use",
        ),
        questionary.Choice(
            f"🔧 Reconfigure  重新配置 {preset.label} 参数",
            value="reconfigure",
        ),
    ]

    return questionary.select(
        f"{preset.label} found, choose action 已有配置，选择操作:",
        choices=choices,
    ).ask()


def _action_no_config(preset: ProviderPreset) -> Optional[str]:
    """When no saved config, choose action
    无存储配置时选择操作

    Returns:
        "configure" | "back" | None
    """
    choices = [
        questionary.Choice(
            f"🔧 Configure  配置 {preset.label} 参数",
            value="configure",
        ),
        questionary.Choice(
            "↩  Go back  返回重新选择",
            value="back",
        ),
    ]

    return questionary.select(
        f"No config for {preset.label}, choose action 无已存储配置，选择操作:",
        choices=choices,
    ).ask()


# ═══════════════════════════════════════════════════════════
#  Guidance & interactive configuration
#  引导 & 交互式配置
# ═══════════════════════════════════════════════════════════

def _show_guidance(provider_name: ProviderName) -> None:
    """Display setup guidance for a provider
    显示提供商的设置引导
    """
    guidance = get_provider_guidance(provider_name)
    if guidance:
        print()
        for line in guidance:
            if line == "":
                print()
            else:
                ui.console.print(f"  [dim]{line}[/]")
        print()

        ready = questionary.confirm(
            "Ready? Continue  已准备好，继续配置:",
            default=True,
        ).ask()
        if not ready:
            ui.hint("请按照上述步骤准备好环境后重新运行 claude-adapter-py")
            raise typer.Exit(0)


def _configure_provider(
    provider_name: ProviderName,
    preset: ProviderPreset,
) -> AdapterConfig:
    """Interactive provider configuration
    交互式提供商配置
    """
    ui.header(f"Configure {preset.label}  配置参数")

    existing = load_provider_config(provider_name)

    # ── API Key ──
    api_key = preset.api_key_placeholder
    if preset.api_key_required:
        default_key = existing.api_key if existing else ""
        api_key_input = questionary.text(
            f"API Key  {preset.api_key_placeholder}:",
            default=default_key,
        ).ask()
        if api_key_input:
            api_key = api_key_input

    # ── Base URL ──
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

    tool_format = questionary.select(
        "Tool calling format 工具调用格式:",
        choices=[native_choice, xml_choice],
        default=default_fmt,
    ).ask()

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
        max_context_window=preset.max_context_window,
    )

    save_provider_config(config)
    set_active_provider(provider_name)

    ui.success(f"Saved {preset.label} configuration")
    return config


# ═══════════════════════════════════════════════════════════
#  Display config & start server
#  显示配置 & 启动服务器
# ═══════════════════════════════════════════════════════════

def _display_config(config: AdapterConfig, preset: ProviderPreset, port: Optional[int]) -> None:
    """Display current configuration summary 显示当前配置摘要"""
    print()
    ui.table([
        ("Provider", preset.label),
        ("Base URL", config.base_url),
        ("Port", str(port or config.port or 3080)),
        ("Opus", config.models.opus),
        ("Sonnet", config.models.sonnet),
        ("Haiku", config.models.haiku),
        ("Tool Format", config.tool_format),
    ])


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
#  Main CLI callback
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
    #  Main loop: always starts with provider selection
    #  主循环：始终从选择供应商开始
    # ══════════════════════════════════════════════════

    while True:
        # ── Select provider 选择提供商 ──
        provider_name = _select_provider()
        if not provider_name:
            ui.warning("No provider selected")
            raise typer.Exit(0)

        preset = get_provider_preset(provider_name)
        existing = load_provider_config(provider_name)

        if existing and not reconfigure:
            # ── Has saved config 已有存储配置 ──
            action = _action_has_config(preset)

            if action == "use":
                set_active_provider(provider_name)
                _display_config(existing, preset, port)
                _update_claude_and_start(existing, port, no_claude_settings)
                return

            elif action == "reconfigure":
                _show_guidance(provider_name)
                config = _configure_provider(provider_name, preset)
                _display_config(config, preset, port)
                _update_claude_and_start(config, port, no_claude_settings)
                return

            else:
                raise typer.Exit(0)

        else:
            # ── No saved config 无存储配置 ──
            action = _action_no_config(preset)

            if action == "configure":
                _show_guidance(provider_name)
                config = _configure_provider(provider_name, preset)
                _display_config(config, preset, port)
                _update_claude_and_start(config, port, no_claude_settings)
                return

            elif action == "back":
                # Loop back to provider selection
                # 返回重新选择供应商
                continue

            else:
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
    tbl.add_column("Base URL")
    tbl.add_column("Models")
    tbl.add_column("Active", justify="center")

    for pname in saved:
        config = load_provider_config(pname)
        if not config:
            continue

        preset = get_provider_preset(pname)
        is_active = "✔" if pname == active else ""

        models_str = config.models.opus
        if config.models.sonnet != config.models.opus:
            models_str += f", {config.models.sonnet}"
        if config.models.haiku not in [config.models.opus, config.models.sonnet]:
            models_str += f", {config.models.haiku}"

        tbl.add_row(preset.label, config.base_url, models_str, is_active)

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

    config = load_provider_config(provider_name)
    if not config:
        ui.warning(f"No saved configuration for {provider}")
        return

    if not force:
        preset = get_provider_preset(provider_name)
        confirm = questionary.confirm(
            f"Remove configuration for {preset.label}?",
            default=False,
        ).ask()
        if not confirm:
            ui.info("Cancelled")
            return

    delete_provider_config(provider_name)

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
