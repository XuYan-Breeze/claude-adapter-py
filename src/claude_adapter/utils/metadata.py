"""Metadata management 元数据管理

Functions for managing adapter metadata
管理适配器元数据的函数
"""

import json
import secrets
import platform
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

from .file_storage import ensure_dir_exists, get_base_dir

# Version - should match pyproject.toml 版本 - 应与 pyproject.toml 匹配
CURRENT_VERSION = "1.0.0"

METADATA_FILE = get_base_dir() / "metadata.json"


class Metadata(BaseModel):
    """Metadata model 元数据模型
    
    Attributes:
        user_id: Unique user ID 唯一用户 ID
        platform: OS platform 操作系统平台
        platform_release: OS version 操作系统版本
        current_version: Current adapter version 当前适配器版本
        latest_version: Latest available version 最新可用版本
        latest_version_timestamp: Cache timestamp 缓存时间戳
        created_at: First run timestamp 首次运行时间戳
    """

    user_id: str
    platform: str
    platform_release: str
    current_version: str
    latest_version: Optional[str] = None
    latest_version_timestamp: Optional[int] = None
    created_at: str


def _generate_user_id() -> str:
    """Generate a unique user ID 生成唯一用户 ID
    
    Returns:
        Random hex string 随机十六进制字符串
    """
    return secrets.token_hex(16)


def _get_os_name() -> str:
    """Get OS name 获取操作系统名称
    
    Returns:
        OS name 操作系统名称
    """
    return platform.system()


def _load_metadata() -> Optional[Metadata]:
    """Load metadata from file 从文件加载元数据
    
    Returns:
        Metadata or None 元数据或 None
    """
    if not METADATA_FILE.exists():
        return None
    
    try:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Metadata(**data)
    except Exception:
        return None


def _save_metadata(metadata: Metadata) -> None:
    """Save metadata to file 将元数据保存到文件
    
    Args:
        metadata: Metadata to save 要保存的元数据
    """
    try:
        ensure_dir_exists(get_base_dir())
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(metadata.model_dump(), f, indent=2, ensure_ascii=False)
    except Exception:
        pass  # Silently fail 静默失败


def get_metadata() -> Metadata:
    """Get or create metadata 获取或创建元数据
    
    Creates new metadata on first run, updates current version on subsequent runs
    首次运行时创建新元数据，后续运行时更新当前版本
    
    Returns:
        Metadata 元数据
    """
    from datetime import datetime
    
    metadata = _load_metadata()
    
    if metadata is None:
        # First run - create new metadata 首次运行 - 创建新元数据
        metadata = Metadata(
            user_id=_generate_user_id(),
            platform=_get_os_name(),
            platform_release=platform.release(),
            current_version=CURRENT_VERSION,
            created_at=datetime.now().isoformat(),
        )
        _save_metadata(metadata)
    else:
        # Update current version if changed 如果更改则更新当前版本
        if metadata.current_version != CURRENT_VERSION:
            metadata.current_version = CURRENT_VERSION
            _save_metadata(metadata)
    
    return metadata


def update_latest_version(version: str) -> None:
    """Update latest version in metadata 更新元数据中的最新版本
    
    Args:
        version: Latest version 最新版本
    """
    import time
    
    metadata = _load_metadata()
    if metadata:
        metadata.latest_version = version
        metadata.latest_version_timestamp = int(time.time())
        _save_metadata(metadata)


def get_cached_latest_version() -> Optional[tuple[str, int]]:
    """Get cached latest version info 获取缓存的最新版本信息
    
    Returns:
        (version, timestamp) or None (版本, 时间戳) 或 None
    """
    metadata = _load_metadata()
    if metadata and metadata.latest_version and metadata.latest_version_timestamp:
        return (metadata.latest_version, metadata.latest_version_timestamp)
    return None
