import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import bleach
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, model_validator
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.extension import _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("sams.errors")
if not logger.handlers:
    file_handler = logging.FileHandler(LOG_DIR / "error.log")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.setLevel(logging.ERROR)


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return bleach.clean(value, tags=[], attributes={}, protocols=[], strip=True)
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    return value


class SanitizedModel(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def sanitize_all_text_fields(cls, value: Any) -> Any:
        return _sanitize_value(value)


class SanitizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.url.path.startswith("/api/"):
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                body = await request.body()
                if body:
                    try:
                        payload = json.loads(body.decode("utf-8"))
                        sanitized = _sanitize_value(payload)
                        new_body = json.dumps(sanitized).encode("utf-8")

                        async def receive() -> dict[str, Any]:
                            return {"type": "http.request", "body": new_body, "more_body": False}

                        request._receive = receive  # type: ignore[attr-defined]
                    except json.JSONDecodeError:
                        pass
        return await call_next(request)


def setup_security(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SanitizationMiddleware)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception at %s", request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred. Please contact support.",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
