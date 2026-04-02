import time
import uuid
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.logger import get_logger
from app.presentation.auth_routes import router as auth_router
from app.presentation.analysis_routes import router as analysis_router

logger = get_logger("app.main")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="CV Review API",
        description="AI-powered CV analysis and optimization system",
        version="1.0.0",
        debug=settings.DEBUG,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request Logging Middleware ────────────────────────────────
    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        method = request.method
        path = request.url.path
        client = request.client.host if request.client else "unknown"

        logger.info(f"[{request_id}] ▶ {method} {path} (client={client})")

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration = (time.perf_counter() - start) * 1000
            logger.error(
                f"[{request_id}] ✖ {method} {path} — unhandled exception "
                f"after {duration:.0f}ms\n{traceback.format_exc()}"
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error"},
            )

        duration = (time.perf_counter() - start) * 1000
        status = response.status_code
        level = "info" if status < 400 else ("warning" if status < 500 else "error")
        getattr(logger, level)(
            f"[{request_id}] ◀ {method} {path} → {status} ({duration:.0f}ms)"
        )
        return response

    # ── Global Exception Handler ─────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", "???")
        logger.error(
            f"[{rid}] Unhandled: {type(exc).__name__}: {exc}\n"
            f"{traceback.format_exc()}"
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error"},
        )

    # Routes
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(analysis_router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    logger.info("🚀 CV Review API started (debug=%s)", settings.DEBUG)
    return app


app = create_app()
