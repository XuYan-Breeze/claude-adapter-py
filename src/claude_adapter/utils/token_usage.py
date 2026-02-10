"""Token usage tracking Token 使用跟踪

Functions for recording token usage statistics
记录 Token 使用统计的函数
"""

from datetime import datetime
from typing import Optional

from .file_storage import get_base_dir, append_json_line, get_today_date_string

# Token usage directory Token 使用目录
TOKEN_USAGE_DIR = get_base_dir() / "token_usage"


def record_usage(
    provider: str,
    model_name: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: Optional[int] = None,
    streaming: bool = False,
) -> None:
    """Record token usage 记录 Token 使用
    
    Args:
        provider: Provider URL 提供商 URL
        model_name: Original model name 原始模型名称
        model: Actual model name 实际模型名称
        input_tokens: Input tokens 输入 token 数
        output_tokens: Output tokens 输出 token 数
        cached_input_tokens: Cached input tokens 缓存的输入 token 数
        streaming: Whether streaming 是否流式
    """
    record = {
        "timestamp": datetime.now().isoformat(),
        "provider": provider,
        "model_name": model_name,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "streaming": streaming,
    }
    
    if cached_input_tokens:
        record["cached_input_tokens"] = cached_input_tokens
    
    # Append to today's file 追加到今天的文件
    file_path = TOKEN_USAGE_DIR / f"{get_today_date_string()}.jsonl"
    append_json_line(file_path, record)
