
import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router, _app_service, get_app_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting L4MOLE API server...")

    get_app_service()

    yield

    logger.info("Shutting down L4MOLE API server...")
    global _app_service
    from . import routes
    if routes._app_service is not None:
        routes._app_service.close()
        routes._app_service = None


def create_app(
    title: str = "Local Semantic Explorer API",
    description: str = "Local Semantic Explorer REST API",
    version: str = "1.0.0",
    cors_origins: Optional[list] = None,
) -> FastAPI:

    app = FastAPI(
        title=title,
        description=description,
        version=version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    if cors_origins is None:
        cors_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.get("/")
    async def root():
        return {
            "name": "Local Semantic Explorer API",
            "version": version,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


class APIServer:

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        log_level: str = "info",
    ):
        self.host = host
        self.port = port
        self.log_level = log_level
        self.app = create_app()
        self._server = None

    def run(self):
        import uvicorn

        def signal_handler(_sig, _frame):
            logger.info("Received shutdown signal")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level=self.log_level,
        )

    async def start(self):
        import uvicorn

        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level=self.log_level,
        )
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def stop(self):
        if self._server:
            self._server.should_exit = True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="L4MOLE REST API Server")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Log level (default: info)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    server = APIServer(
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )
    server.run()


if __name__ == "__main__":
    main()
