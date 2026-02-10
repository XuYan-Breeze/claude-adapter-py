"""Error logging 错误日志

Functions for recording error details
记录错误详情的函数
"""

from datetime import datetime
from typing import Any, Optional

from .file_storage import get_base_dir, append_json_line, get_today_date_string

# Error log directory 错误日志目录
ERROR_LOG_DIR = get_base_dir() / "error_logs"

# Status codes to skip (user-related errors) 要跳过的状态码（用户相关错误）
SKIP_STATUS_CODES = {401, 402, 404, 429}


def record_error(
    error: Exception,
    request_id: str,
    provider: str,
    model_name: str,
    streaming: bool,
) -> None:
    """Record error details 记录错误详情
    
    Args:
        error: Exception 异常
        request_id: Request ID 请求 ID
        provider: Provider URL 提供商 URL
        model_name: Model name 模型名称
        streaming: Whether streaming 是否流式
    """
    # Extract status code if available 如果可用则提取状态码
    status_code: Optional[int] = None
    if hasattr(error, "status_code"):
        status_code = error.status_code  # type: ignore
    elif hasattr(error, "status"):
        status_code = error.status  # type: ignore
    
    # Skip user-related errors 跳过用户相关错误
    if status_code in SKIP_STATUS_CODES:
        return
    
    # Build error record 构建错误记录
    error_dict: dict[str, Any] = {
        "message": str(error),
    }
    
    if status_code:
        error_dict["status"] = status_code
    
    if hasattr(error, "code"):
        error_dict["code"] = error.code  # type: ignore
    
    if hasattr(error, "type"):
        error_dict["type"] = error.type  # type: ignore
    
    if hasattr(error, "response"):
        try:
            error_dict["response"] = str(error.response)  # type: ignore
        except Exception:
            pass
    
    record = {
        "timestamp": datetime.now().isoformat(),
        "request_id": request_id,
        "provider": provider,
        "model_name": model_name,
        "streaming": streaming,
        "error": error_dict,
    }
    
    # Append to today's file 追加到今天的文件
    file_path = ERROR_LOG_DIR / f"{get_today_date_string()}.jsonl"
    append_json_line(file_path, record)
