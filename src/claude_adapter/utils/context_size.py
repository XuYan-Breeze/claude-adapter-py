"""Context window size parsing and formatting 上下文窗口解析与格式化

Supports human-readable formats: 128k, 200k, 256k, 131072
支持人类可读格式：128k、200k、256k、131072
"""


def parse_context_size(s: str) -> int:
    """Parse context size from string. Accepts 128k, 200k, 256k or raw numbers.

    解析上下文长度字符串，支持 128k、200k、256k 或纯数字。

    Args:
        s: Input string (e.g. "128k", "200k", "131072")

    Returns:
        Token count as integer

    Raises:
        ValueError: If input cannot be parsed
    """
    if not s or not s.strip():
        raise ValueError("Empty input")
    raw = s.strip().lower()
    if raw.endswith("k"):
        return int(raw[:-1]) * 1024
    if raw.endswith("m"):
        return int(raw[:-1]) * 1024 * 1024
    return int(raw)


def format_context_size(n: int) -> str:
    """Format token count as human-readable string (e.g. 131072 -> 128k).

    将 token 数量格式化为可读字符串（如 131072 -> 128k）。

    Args:
        n: Token count

    Returns:
        Formatted string like "128k" or raw number if not round
    """
    if n >= 1024 and n % 1024 == 0:
        return f"{n // 1024}k"
    if n >= 1024 * 1024 and n % (1024 * 1024) == 0:
        return f"{n // (1024 * 1024)}m"
    return str(n)
