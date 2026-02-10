"""Logging utilities 日志工具

Structured logger with levels and timestamps
带级别和时间戳的结构化日志器
"""

import os
import sys
from datetime import datetime
from enum import IntEnum
from typing import Any, Optional


class LogLevel(IntEnum):
    """Log levels 日志级别"""

    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3


# ANSI color codes ANSI 颜色代码
_C_GRAY = "\033[90m"
_C_CYAN = "\033[36m"
_C_YELLOW = "\033[33m"
_C_RED = "\033[31m"
_C_GREEN = "\033[32m"
_C_DIM = "\033[2m"
_C_BOLD = "\033[1m"
_C_RESET = "\033[0m"

_LEVEL_STYLE = {
    LogLevel.DEBUG: (_C_GRAY, "DBG"),
    LogLevel.INFO: (_C_CYAN, "INF"),
    LogLevel.WARN: (_C_YELLOW, "WRN"),
    LogLevel.ERROR: (_C_RED, "ERR"),
}


class Logger:
    """Structured logger 结构化日志器

    Provides leveled logging with colored, aligned output
    提供带彩色对齐输出的分级日志

    Attributes:
        level: Current log level 当前日志级别
        prefix: Log prefix 日志前缀
    """

    def __init__(self, prefix: str = "adapter"):
        """Initialize logger 初始化日志器

        Args:
            prefix: Log prefix 日志前缀
        """
        self.prefix = prefix
        level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        self.level = self._parse_level(level_str)

    def _parse_level(self, level: str) -> LogLevel:
        """Parse log level string 解析日志级别字符串"""
        return {
            "DEBUG": LogLevel.DEBUG,
            "INFO": LogLevel.INFO,
            "WARN": LogLevel.WARN,
            "ERROR": LogLevel.ERROR,
        }.get(level, LogLevel.INFO)

    @staticmethod
    def _ts() -> str:
        """Short HH:MM:SS timestamp 短格式时间戳"""
        return datetime.now().strftime("%H:%M:%S")

    @staticmethod
    def _format_meta(meta: Optional[dict[str, Any]]) -> str:
        """Format metadata as a clean key=value string
        将元数据格式化为干净的 key=value 字符串

        Args:
            meta: Metadata dict 元数据字典

        Returns:
            Formatted string 格式化字符串
        """
        if not meta:
            return ""
        # Filter out None values and build aligned pairs
        # 过滤 None 值并构建对齐的键值对
        pairs = [f"{k}={v}" for k, v in meta.items() if v is not None]
        if not pairs:
            return ""
        return f" {_C_DIM}({', '.join(pairs)}){_C_RESET}"

    def _log(self, level: LogLevel, message: str, meta: Optional[dict[str, Any]] = None) -> None:
        """Internal log method 内部日志方法"""
        if level < self.level:
            return

        color, tag = _LEVEL_STYLE[level]
        ts = self._ts()
        meta_str = self._format_meta(meta)

        # Format: HH:MM:SS TAG message (key=val, key=val)
        output = f"{_C_DIM}{ts}{_C_RESET} {color}{tag}{_C_RESET} {message}{meta_str}"

        stream = sys.stderr if level == LogLevel.ERROR else sys.stdout
        print(output, file=stream)

    # ── public API ──

    def debug(self, message: str, meta: Optional[dict[str, Any]] = None) -> None:
        """Log debug message 记录调试消息"""
        self._log(LogLevel.DEBUG, message, meta)

    def info(self, message: str, meta: Optional[dict[str, Any]] = None) -> None:
        """Log info message 记录信息消息"""
        self._log(LogLevel.INFO, message, meta)

    def warn(self, message: str, meta: Optional[dict[str, Any]] = None) -> None:
        """Log warning message 记录警告消息"""
        self._log(LogLevel.WARN, message, meta)

    def error(
        self,
        message: str,
        error: Optional[Exception] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log error message 记录错误消息"""
        error_meta = {**meta} if meta else {}
        if error:
            error_meta["error"] = str(error)
        self._log(LogLevel.ERROR, message, error_meta)

    def with_request_id(self, request_id: str) -> "RequestLogger":
        """Create a request-scoped logger 创建请求作用域的日志器"""
        return RequestLogger(self, request_id)


class RequestLogger:
    """Request-scoped logger 请求作用域的日志器

    Prefixes every line with a short request tag for visual grouping
    为每行加上短请求标签以便视觉分组
    """

    def __init__(self, parent: Logger, request_id: str):
        self.parent = parent
        # Use last 8 chars as short ID for readability
        # 使用后 8 个字符作为短 ID 以提高可读性
        self.short_id = request_id[-8:] if len(request_id) > 8 else request_id

    def _fmt(self, message: str, meta: Optional[dict[str, Any]] = None) -> tuple[str, dict[str, Any]]:
        """Prepend short request tag to message
        在消息前添加短请求标签"""
        tagged = f"{_C_DIM}[{self.short_id}]{_C_RESET} {message}"
        return tagged, meta or {}

    def debug(self, message: str, meta: Optional[dict[str, Any]] = None) -> None:
        msg, m = self._fmt(message, meta)
        self.parent.debug(msg, m)

    def info(self, message: str, meta: Optional[dict[str, Any]] = None) -> None:
        msg, m = self._fmt(message, meta)
        self.parent.info(msg, m)

    def warn(self, message: str, meta: Optional[dict[str, Any]] = None) -> None:
        msg, m = self._fmt(message, meta)
        self.parent.warn(msg, m)

    def error(
        self,
        message: str,
        error: Optional[Exception] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> None:
        msg, m = self._fmt(message, meta)
        self.parent.error(msg, error, m)


# Global logger instance 全局日志器实例
logger = Logger()
