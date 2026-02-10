"""Version update checking 版本更新检查

Functions for checking latest version from PyPI
从 PyPI 检查最新版本的函数
"""

import time
from typing import Optional
import httpx
from packaging import version

from .metadata import get_cached_latest_version, update_latest_version, CURRENT_VERSION

# Cache validity duration (24 hours) 缓存有效期（24 小时）
CACHE_DURATION = 24 * 60 * 60


class UpdateInfo:
    """Update information 更新信息
    
    Attributes:
        current: Current version 当前版本
        latest: Latest version 最新版本
        has_update: Whether update available 是否有可用更新
    """

    def __init__(self, current: str, latest: str, has_update: bool):
        self.current = current
        self.latest = latest
        self.has_update = has_update


def _is_cache_valid(timestamp: int) -> bool:
    """Check if cache is still valid 检查缓存是否仍然有效
    
    Args:
        timestamp: Cache timestamp 缓存时间戳
        
    Returns:
        True if valid 如果有效则为 True
    """
    return (time.time() - timestamp) < CACHE_DURATION


def _is_newer_version(latest: str, current: str) -> bool:
    """Compare versions 比较版本
    
    Args:
        latest: Latest version 最新版本
        current: Current version 当前版本
        
    Returns:
        True if latest is newer 如果最新版本更新则为 True
    """
    try:
        return version.parse(latest) > version.parse(current)
    except Exception:
        return False


async def _fetch_latest_version() -> Optional[str]:
    """Fetch latest version from PyPI 从 PyPI 获取最新版本
    
    Returns:
        Latest version or None 最新版本或 None
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get("https://pypi.org/pypi/claude-adapter-py/json")
            if response.status_code == 200:
                data = response.json()
                return data["info"]["version"]
    except Exception:
        pass
    return None


async def check_for_updates() -> Optional[UpdateInfo]:
    """Check for updates (with caching) 检查更新（带缓存）
    
    Returns:
        Update info or None 更新信息或 None
    """
    # Check cache first 首先检查缓存
    cached = get_cached_latest_version()
    if cached:
        cached_version, cached_timestamp = cached
        if _is_cache_valid(cached_timestamp):
            has_update = _is_newer_version(cached_version, CURRENT_VERSION)
            return UpdateInfo(CURRENT_VERSION, cached_version, has_update)
    
    # Fetch from PyPI 从 PyPI 获取
    latest = await _fetch_latest_version()
    if latest:
        update_latest_version(latest)
        has_update = _is_newer_version(latest, CURRENT_VERSION)
        return UpdateInfo(CURRENT_VERSION, latest, has_update)
    
    return None


def get_cached_update_info() -> Optional[UpdateInfo]:
    """Get cached update info synchronously 同步获取缓存的更新信息
    
    Returns:
        Update info or None 更新信息或 None
    """
    cached = get_cached_latest_version()
    if cached:
        cached_version, cached_timestamp = cached
        if _is_cache_valid(cached_timestamp):
            has_update = _is_newer_version(cached_version, CURRENT_VERSION)
            return UpdateInfo(CURRENT_VERSION, cached_version, has_update)
    return None
