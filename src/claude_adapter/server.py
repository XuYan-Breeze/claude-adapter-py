"""FastAPI server FastAPI 服务器

HTTP server for Claude Adapter
Claude Adapter 的 HTTP 服务器
"""

import socket
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models.config import AdapterConfig
from .handlers.messages import handle_messages_request
from .utils.logger import logger
from .utils.update import check_for_updates


# Global config reference 全局配置引用
_config: AdapterConfig | None = None


def set_config(config: AdapterConfig) -> None:
    """Set global configuration 设置全局配置
    
    Args:
        config: Adapter configuration 适配器配置
    """
    global _config
    _config = config


def get_config() -> AdapterConfig:
    """Get global configuration 获取全局配置
    
    Returns:
        Adapter configuration 适配器配置
        
    Raises:
        RuntimeError: If config not set 如果配置未设置
    """
    if _config is None:
        raise RuntimeError("Configuration not set")
    return _config


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler 应用程序生命周期处理器
    
    Runs on startup and shutdown
    在启动和关闭时运行
    """
    # Startup 启动
    logger.info("Server starting up")
    
    # Check for updates (non-blocking) 检查更新（非阻塞）
    try:
        update_info = await check_for_updates()
        if update_info and update_info.has_update:
            logger.info(f"Update available: {update_info.current} → {update_info.latest}")
    except Exception:
        pass  # Silently fail 静默失败
    
    yield
    
    # Shutdown 关闭
    logger.info("Server shutting down")


def create_app() -> FastAPI:
    """Create FastAPI application 创建 FastAPI 应用程序
    
    Returns:
        FastAPI app FastAPI 应用
    """
    app = FastAPI(
        title="Claude Adapter",
        description="Anthropic API adapter for OpenAI-compatible endpoints",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # Add CORS middleware 添加 CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint 健康检查端点
        
        Returns:
            Status dict 状态字典
        """
        return {"status": "ok"}
    
    @app.post("/v1/messages")
    async def messages(request: Request):
        """POST /v1/messages endpoint
        
        Anthropic Messages API compatible endpoint
        兼容 Anthropic Messages API 的端点
        """
        config = get_config()
        return await handle_messages_request(request, config)
    
    return app


def find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """Find an available port 查找可用端口
    
    Args:
        start_port: Starting port to try 开始尝试的端口
        max_attempts: Maximum number of ports to try 最大尝试端口数
        
    Returns:
        Available port number 可用端口号
        
    Raises:
        RuntimeError: If no port available 如果没有可用端口
    """
    for port in range(start_port, start_port + max_attempts):
        try:
            # Try to bind to the port 尝试绑定端口
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            
            # If connection failed, port is available 如果连接失败，端口可用
            if result != 0:
                return port
        except Exception:
            continue
    
    raise RuntimeError(f"No available port found in range {start_port}-{start_port + max_attempts}")


async def run_server(config: AdapterConfig, port: int | None = None) -> None:
    """Run the FastAPI server 运行 FastAPI 服务器
    
    Args:
        config: Adapter configuration 适配器配置
        port: Server port (None for auto) 服务器端口（None 表示自动）
    """
    import uvicorn
    
    # Set global config 设置全局配置
    set_config(config)
    
    # Find available port if not specified 如果未指定则查找可用端口
    if port is None:
        port = config.port or 3080
    
    try:
        server_port = find_available_port(port)
        if server_port != port:
            logger.warn(f"Port {port} unavailable, using {server_port}")
    except RuntimeError as e:
        logger.error(str(e))
        return
    
    logger.info(f"Server listening on http://127.0.0.1:{server_port}")
    
    # Create app 创建应用
    app = create_app()
    
    # Run server 运行服务器
    config_uvicorn = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=server_port,
        log_level="warning",  # Reduce uvicorn logs 减少 uvicorn 日志
    )
    server = uvicorn.Server(config_uvicorn)
    await server.serve()
