"""File storage utilities 文件存储工具

Shared utilities for managing daily JSON files
管理每日 JSON 文件的共享工具
"""

import json
from datetime import datetime
from pathlib import Path

# Base directory for all adapter data 所有适配器数据的基础目录
BASE_DIR = Path.home() / ".claude-adapter"


def get_today_date_string() -> str:
    """Get today's date as YYYY-MM-DD string
    获取今天的日期字符串（YYYY-MM-DD 格式）
    
    Returns:
        Date string 日期字符串
    """
    return datetime.now().strftime("%Y-%m-%d")


def ensure_dir_exists(dir_path: Path) -> None:
    """Ensure a directory exists, creating it if necessary
    确保目录存在，如有必要则创建
    
    Args:
        dir_path: Directory path 目录路径
    """
    dir_path.mkdir(parents=True, exist_ok=True)


def get_base_dir() -> Path:
    """Get the base storage directory
    获取基础存储目录
    
    Returns:
        Base directory path 基础目录路径
    """
    return BASE_DIR


def append_json_line(file_path: Path, record: dict) -> None:
    """Append a JSON record to a file (one JSON object per line)
    将 JSON 记录追加到文件（每行一个 JSON 对象）
    
    This is atomic on most filesystems and avoids race conditions
    在大多数文件系统上这是原子操作，避免竞态条件
    
    Args:
        file_path: File path 文件路径
        record: JSON record to append 要追加的 JSON 记录
    """
    try:
        # Ensure parent directory exists 确保父目录存在
        ensure_dir_exists(file_path.parent)
        
        # Append JSON line 追加 JSON 行
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # Silently fail - logging operations should not break the app
        # 静默失败 - 日志操作不应中断应用
        pass
