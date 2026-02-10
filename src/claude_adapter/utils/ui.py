"""Terminal UI utilities 终端 UI 工具

Functions for formatted terminal output using rich
使用 rich 进行格式化终端输出的函数
"""

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich import box

# Create console instance 创建控制台实例
console = Console()

# ─── Color palette 调色板 ───
BRAND = "#D97757"
ERROR = "#D95858"
WARNING = "#D9A458"
DIM = "#6B6B6B"
TEXT = "#E6E6E6"
HIGHLIGHT = "#A78BFA"

# Banner 专用色
BORDER = "#8B7355"
ACCENT = "#E8A87C"
FREE_TAG = "#81C784"
PAID_TAG = "#64B5F6"
ARROW = "#B39DDB"
TITLE = "#FF8A65"

# 渐变色列表 gradient colors for ASCII art
GRAD = ["#FF6B35", "#FF8A65", "#FFAB91", "#FFE0B2", "#FFF3E0",
        "#E1BEE7", "#CE93D8", "#BA68C8"]


def _gradient_bar(width: int, reverse: bool = False) -> Text:
    """Create a gradient bar with fade-in/out using block characters
    使用方块字符创建带淡入淡出的渐变条

    Args:
        width: bar width in characters  条宽（字符数）
        reverse: if True, reverse the gradient direction  反转渐变方向
    """
    # 暖 → 冷渐变色板 (warm orange → coral → purple → blue)
    stops = [
        "#FF6B35", "#FF7B45", "#FF8A55", "#FF9966",
        "#FFAB78", "#FFBB88", "#F0A8C0", "#D99BDA",
        "#C08BE8", "#A87BF0", "#9370DB", "#7B68EE",
    ]
    if reverse:
        stops = stops[::-1]

    # 渐进符号：淡入 → 实心 → 淡出 (fade-in → solid → fade-out)
    fade_in = ["░", "░", "▒", "▓"]
    fade_out = ["▓", "▒", "░", "░"]
    fi, fo = len(fade_in), len(fade_out)

    bar = Text()
    for i in range(width):
        idx = int(i / max(width - 1, 1) * (len(stops) - 1))
        if i < fi:
            ch = fade_in[i]
        elif i >= width - fo:
            ch = fade_out[i - (width - fo)]
        else:
            ch = "█"
        bar.append(ch, style=f"bold {stops[idx]}")
    return bar


def _gradient_text(text: str, bold: bool = True) -> Text:
    """Apply character-level gradient to text 对文本应用字符级渐变

    Args:
        text: the text to colorize  待着色文本
        bold: whether to apply bold style  是否加粗
    """
    stops = [
        "#FF6B35", "#FF8A55", "#FFAB78", "#F0A8C0",
        "#D99BDA", "#C08BE8", "#A87BF0", "#7B68EE",
    ]
    out = Text()
    visible = [c for c in text if c != " "]
    n = max(len(visible) - 1, 1)
    vi = 0
    for ch in text:
        if ch == " ":
            out.append(ch)
        else:
            idx = int(vi / n * (len(stops) - 1))
            s = f"bold {stops[idx]}" if bold else stops[idx]
            out.append(ch, style=s)
            vi += 1
    return out


def banner() -> None:
    """Display ASCII art banner 显示 ASCII 艺术横幅"""

    BAR_W = 52  # 渐变条宽度

    # ── 顶部渐变条 ──
    top_bar = _gradient_bar(BAR_W)

    # ── 装饰星号行 ──
    stars = Text(justify="center")
    sparkle_chars = ["·", "✦", "·", " ", "·", "✦", "·"]
    sparkle_colors = [DIM, ACCENT, DIM, "", DIM, ACCENT, DIM]
    for ch, co in zip(sparkle_chars, sparkle_colors):
        stars.append(ch, style=f"bold {co}" if co else "")

    # ── 主标题：字符级渐变 ──
    title = _gradient_text("C  L  A  U  D  E     A  D  A  P  T  E  R")

    # ── 小标签 ──
    tag = Text(justify="center")
    tag.append("«", style=f"bold {ACCENT}")
    tag.append(" Multi-provider API Adapter ", style=f"italic {DIM}")
    tag.append("»", style=f"bold {ACCENT}")

    # ── 底部渐变条 ──
    bot_bar = _gradient_bar(BAR_W, reverse=True)

    # ── 功能线 ──
    func_line = Text(justify="center")
    func_line.append("Anthropic", style=f"bold {ACCENT}")
    func_line.append("  ⟷  ", style=f"bold {ARROW}")
    func_line.append("OpenAI-compatible", style=f"bold {ACCENT}")

    # ── 提供商表格 ──
    CUSTOM_TAG = "#FFB74D"

    prov_tbl = Table(
        show_header=False, show_edge=False, box=None,
        padding=(0, 1), expand=False,
    )
    prov_tbl.add_column(justify="right", width=10, no_wrap=True)
    prov_tbl.add_column(justify="left", no_wrap=True)
    prov_tbl.add_row(
        Text("◈ Free", style=f"bold {FREE_TAG}"),
        Text("NVIDIA · Ollama · LM Studio", style=TEXT),
    )
    prov_tbl.add_row(
        Text("◈ Paid", style=f"bold {PAID_TAG}"),
        Text("Kimi · DeepSeek · GLM · MiniMax", style=TEXT),
    )
    prov_tbl.add_row(
        Text("◈ Custom", style=f"bold {CUSTOM_TAG}"),
        Text("OpenAI-compatible endpoint", style=TEXT),
    )

    # ── 底部提示 ──
    tip = Text(justify="center")
    tip.append("claude-adapter-py -h", style=f"bold {HIGHLIGHT}")
    tip.append("  for help", style=DIM)

    # ── 组装 ──
    body = Group(
        Align.center(top_bar),
        Align.center(stars),
        Text(""),
        Align.center(title),
        Align.center(tag),
        Text(""),
        Align.center(stars),
        Align.center(bot_bar),
        Text(""),
        Align.center(func_line),
        Text(""),
        Align.center(prov_tbl),
        Text(""),
        Align.center(tip),
    )

    console.print()
    console.print(
        Panel(
            body,
            box=box.ROUNDED,
            border_style=BORDER,
            title=f"[bold {BRAND}]  ◆  claude-adapter-py  ◆  [/]",
            title_align="center",
            subtitle=f"[{DIM}]v1.0 · Python 3.12+[/]",
            subtitle_align="center",
            padding=(1, 3),
            width=62,
        )
    )
    console.print()


def header(subtitle: str) -> None:
    """Display header with subtitle 显示带副标题的标题"""
    console.print()
    console.print(f"  [bold #8D6E63]{subtitle}[/]")
    console.print()


def info(message: str) -> None:
    """Display info message 显示信息消息"""
    console.print(f"[#64B5F6]•[/] {message}", style=TEXT)


def success(message: str) -> None:
    """Display success message 显示成功消息"""
    console.print(f"[bold #81C784]✔[/] [bold #81C784]{message}[/]")


def warning(message: str) -> None:
    """Display warning message 显示警告消息"""
    console.print(f"[bold #FFB74D]⚠[/] [bold #FFB74D]{message}[/]")


def error(message: str, err: Exception | None = None) -> None:
    """Display error message 显示错误消息"""
    console.print(f"[bold #E57373]✖[/] [bold #E57373]{message}[/]")
    if err:
        console.print(f"  [dim #E57373]{str(err)}[/]")


def status_done(success_status: bool, text: str = "") -> None:
    """Display status completion 显示状态完成"""
    if success_status:
        console.print(f"[#81C784]✔[/] [dim]{text}[/]")
    else:
        console.print(f"[#E57373]✖[/] [dim]{text}[/]")


def hint(text: str) -> None:
    """Display hint message 显示提示消息"""
    console.print(f"  {text}", style=DIM)


def table(rows: list[tuple[str, str]]) -> None:
    """Display a key-value table 显示键值表格"""
    console.print()
    max_label_width = max(len(label) for label, _ in rows) if rows else 0
    for label, value in rows:
        padded_label = label.ljust(max_label_width)
        console.print(f"  [dim #8D6E63]{padded_label}[/]  [bold #B39DDB]{value}[/]")
    console.print()


def highlight(text: str) -> str:
    """Highlight text 高亮文本"""
    return f"[{HIGHLIGHT}]{text}[/{HIGHLIGHT}]"


def new_url(url: str) -> str:
    """Format URL with highlight 使用高亮格式化 URL"""
    return f"[bold {HIGHLIGHT} underline]{url}[/bold {HIGHLIGHT} underline]"


def update_notify(current: str, latest: str) -> None:
    """Display update notification 显示更新通知"""
    console.print()
    console.print(
        f"[#64B5F6]•[/] Update available: [dim]{current}[/] [bold #B39DDB]→[/] [bold #81C784]{latest}[/]"
    )
    hint("Run 'pip install --upgrade claude-adapter-py' to update")
