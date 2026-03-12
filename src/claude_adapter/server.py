"""FastAPI server FastAPI 服务器

HTTP server for Claude Adapter
Claude Adapter 的 HTTP 服务器
"""

import asyncio
import signal
import socket
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models.config import AdapterConfig
from .handlers.messages import handle_messages_request, close_openai_client
from .utils.logger import logger
from .utils.update import check_for_updates

DEFAULT_SHUTDOWN_TIMEOUT = 10

# Global config reference 全局配置引用
_config: Optional[AdapterConfig] = None


def set_config(config: AdapterConfig) -> None:
    """Set global configuration 设置全局配置"""
    global _config
    _config = config


def get_config() -> AdapterConfig:
    """Get global configuration 获取全局配置"""
    if _config is None:
        raise RuntimeError("Configuration not set")
    return _config


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler 应用程序生命周期处理器"""
    logger.info("Server starting up")

    try:
        update_info = await check_for_updates()
        if update_info and update_info.has_update:
            logger.info(f"Update available: {update_info.current} → {update_info.latest}")
    except Exception:
        pass

    yield

    try:
        await close_openai_client()
    except Exception:
        pass

    logger.info("Server shutting down")


def create_app() -> FastAPI:
    """Create FastAPI application 创建 FastAPI 应用程序"""
    app = FastAPI(
        title="Claude Adapter",
        description="Anthropic API adapter for OpenAI-compatible endpoints",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "adapter": "claude-adapter-py"}

    @app.post("/v1/messages")
    async def messages(request: Request):
        config = get_config()
        return await handle_messages_request(request, config)

    return app


def find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """Find an available port by actually binding 通过实际绑定查找可用端口"""
    for port in range(start_port, start_port + max_attempts):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", port))
            sock.close()
            return port
        except OSError:
            continue

    raise RuntimeError(f"No available port found in range {start_port}-{start_port + max_attempts}")


async def run_server(config: AdapterConfig, port: Optional[int] = None) -> None:
    """Run the FastAPI server with graceful shutdown 运行带优雅关闭的 FastAPI 服务器"""
    import uvicorn

    set_config(config)

    if port is None:
        port = config.port or 3080

    try:
        server_port = find_available_port(port)
        if server_port != port:
            logger.warn(f"Port {port} unavailable, using {server_port}")
    except RuntimeError as e:
        logger.error(str(e))
        return

    logger.info(f"Server listening on http://0.0.0.0:{server_port}")

    app = create_app()

    uvicorn_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=server_port,
        log_level="warning",
    )
    server = uvicorn.Server(uvicorn_config)

    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        if not shutdown_event.is_set():
            logger.info("Received shutdown signal, closing gracefully...")
            shutdown_event.set()
            server.should_exit = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    serve_task = asyncio.ensure_future(server.serve())

    done, _ = await asyncio.wait(
        [serve_task, asyncio.ensure_future(shutdown_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    if shutdown_event.is_set() and not serve_task.done():
        try:
            await asyncio.wait_for(serve_task, timeout=DEFAULT_SHUTDOWN_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warn("Graceful shutdown timeout exceeded, forcing close")
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass

    if serve_task.done() and not serve_task.cancelled():
        exc = serve_task.exception()
        if exc:
            raise exc
