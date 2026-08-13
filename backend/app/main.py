from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.briefs import router as briefs_router
from app.api.routes.catalog import router as catalog_router
from app.api.routes.health import router as health_router
from app.api.routes.internal_data import router as internal_data_router
from app.api.routes.monitoring import router as monitoring_router
from app.api.routes.recommendations import router as recommendations_router
from app.core.config import get_settings


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": str(exc.detail),
                "details": {},
            }
        },
    )


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Idempotency-Key", "If-Match", "X-CSRF-Token"],
    )
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.include_router(auth_router)
    app.include_router(briefs_router)
    app.include_router(catalog_router)
    app.include_router(internal_data_router)
    app.include_router(monitoring_router)
    app.include_router(recommendations_router)
    app.include_router(health_router)
    return app


app = create_app()
