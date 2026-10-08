"""FastAPI application factory: wires routers, middleware and exception handlers."""

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.db.database import engine
from app.routers import (
    ai_assistant,
    analytics,
    appointments,
    auth,
    departments,
    doctors,
    patients,
    predictions,
)

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    from app.ml.predict import get_predictor

    predictor = get_predictor()
    if predictor.is_loaded:
        logger.info("Loaded model %s (version %s)", predictor.model_name, predictor.model_version)
    else:
        logger.warning("No trained model found at %s - run `python -m app.ml.train`", settings.model_path)
    yield
    engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "Hospital appointment management with ML no-show prediction, SHAP explanations and a grounded "
        "GenAI admin assistant. Authenticate via **POST /api/auth/login** and use the *Authorize* button."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %s (%.1f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code}, headers=headers)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": ".".join(str(p) for p in err["loc"] if p != "body"), "message": err["msg"]} for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": "Validation failed", "code": "validation_error", "errors": errors})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "code": "internal_error"})


for module in (auth, patients, doctors, departments, appointments, predictions, analytics, ai_assistant):
    app.include_router(module.router, prefix=settings.API_PREFIX)


@app.get("/health", tags=["Health"])
def health() -> dict[str, object]:
    from app.ml.predict import get_predictor

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    predictor = get_predictor()
    return {"status": "ok", "database": "ok", "model_loaded": predictor.is_loaded, "model_version": predictor.model_version}
