from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import hashlib
import json
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.background import BackgroundTask

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import AppError, severity_from_status
from app.db.base import Base
from app.db.models import AuditLog, IdempotencyRecord, Project
from app.db.session import engine
from sqlalchemy import text
from sqlalchemy.orm import Session


def _decode_json_safe(data: bytes) -> dict:
    if not data:
        return {}
    try:
        value = json.loads(data.decode())
        if isinstance(value, dict):
            return value
        return {"data": value}
    except Exception:  # noqa: BLE001
        return {"raw_length": len(data)}


def _extract_actor(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    return token or None


def _persist_audit_log(
    *,
    actor_id: str | None,
    actor_role: str | None,
    method: str,
    path: str,
    status_code: int,
    correlation_id: str | None,
    action: str,
    request_payload: dict,
    response_payload: dict,
) -> None:
    with Session(bind=engine) as db:
        db.add(
            AuditLog(
                actor_id=actor_id,
                actor_role=actor_role,
                action=action,
                method=method,
                path=path,
                status_code=status_code,
                correlation_id=correlation_id,
                diff={"request": request_payload, "response": response_payload},
            )
        )
        db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            columns = conn.execute(text("PRAGMA table_info(imports)")).fetchall()
            names = {row[1] for row in columns}
            if "source_rows" not in names and names:
                conn.execute(text("ALTER TABLE imports ADD COLUMN source_rows JSON"))
            campaign_cols = conn.execute(text("PRAGMA table_info(campaign_messages)")).fetchall()
            campaign_names = {row[1] for row in campaign_cols}
            if "manual_fallback_comment" not in campaign_names and campaign_names:
                conn.execute(text("ALTER TABLE campaign_messages ADD COLUMN manual_fallback_comment TEXT"))
            batch_cols = conn.execute(text("PRAGMA table_info(task_batches)")).fetchall()
            batch_names = {row[1] for row in batch_cols}
            if "result" not in batch_names and batch_names:
                conn.execute(text("ALTER TABLE task_batches ADD COLUMN result JSON"))
            if "error" not in batch_names and batch_names:
                conn.execute(text("ALTER TABLE task_batches ADD COLUMN error JSON"))
            if "started_at" not in batch_names and batch_names:
                conn.execute(text("ALTER TABLE task_batches ADD COLUMN started_at DATETIME"))
            if "finished_at" not in batch_names and batch_names:
                conn.execute(text("ALTER TABLE task_batches ADD COLUMN finished_at DATETIME"))
    with Session(bind=engine) as db:
        exists = db.query(Project).filter(Project.id == "system-project").first()
        if not exists:
            db.add(
                Project(
                    id="system-project",
                    project_code="SYSTEM",
                    project_name="System Project",
                    status="active",
                )
            )
            db.commit()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def idempotency_middleware(request: Request, call_next):
        is_mutating = request.method in {"POST", "PATCH", "PUT", "DELETE"}
        if not is_mutating or not request.url.path.startswith(settings.api_prefix):
            return await call_next(request)
        raw_body = await request.body()
        request_json = _decode_json_safe(raw_body)
        actor_id = _extract_actor(request.headers.get("Authorization"))
        actor_role = (request.headers.get("X-Role") or "operator").strip().lower()
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
        action = f"{request.method} {request.url.path}"

        key = request.headers.get("Idempotency-Key")
        request_hash = hashlib.sha256(raw_body).hexdigest()
        now = datetime.utcnow()

        if key:
            with Session(bind=engine) as db:
                existing = (
                    db.query(IdempotencyRecord)
                    .filter(
                        IdempotencyRecord.key == key,
                        IdempotencyRecord.method == request.method,
                        IdempotencyRecord.path == request.url.path,
                        IdempotencyRecord.expires_at > now,
                    )
                    .order_by(IdempotencyRecord.created_at.desc())
                    .first()
                )
                if existing:
                    if existing.request_hash != request_hash:
                        payload = {
                            "code": "IDEMPOTENCY_KEY_REUSED",
                            "message": "Idempotency-Key уже использован с другим payload",
                            "details": {"method": request.method, "path": request.url.path},
                            "retryable": False,
                            "correlation_id": correlation_id,
                            "severity": "warning",
                        }
                        return JSONResponse(
                            status_code=status.HTTP_409_CONFLICT,
                            content=payload,
                            background=BackgroundTask(
                                _persist_audit_log,
                                actor_id=actor_id,
                                actor_role=actor_role,
                                method=request.method,
                                path=request.url.path,
                                status_code=status.HTTP_409_CONFLICT,
                                correlation_id=correlation_id,
                                action=action,
                                request_payload=request_json,
                                response_payload=payload,
                            ),
                        )
                    return JSONResponse(
                        status_code=existing.status_code,
                        content=existing.response_body,
                        headers={"X-Idempotent-Replay": "true"},
                        background=BackgroundTask(
                            _persist_audit_log,
                            actor_id=actor_id,
                            actor_role=actor_role,
                            method=request.method,
                            path=request.url.path,
                            status_code=existing.status_code,
                            correlation_id=correlation_id,
                            action=f"{action} [replay]",
                            request_payload=request_json,
                            response_payload=existing.response_body,
                        ),
                    )

        response = await call_next(request)
        captured = b""
        async for chunk in response.body_iterator:
            captured += chunk
        replayable_response = Response(
            content=captured,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
        if response.status_code >= 500:
            return replayable_response
        response_json = _decode_json_safe(captured)

        if key:
            with Session(bind=engine) as db:
                db.add(
                    IdempotencyRecord(
                        key=key,
                        method=request.method,
                        path=request.url.path,
                        request_hash=request_hash,
                        status_code=response.status_code,
                        response_body=response_json,
                        expires_at=now + timedelta(hours=settings.idempotency_ttl_hours),
                    )
                )
                db.commit()

        replayable_response.background = BackgroundTask(
            _persist_audit_log,
            actor_id=actor_id,
            actor_role=actor_role,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            correlation_id=correlation_id,
            action=action,
            request_payload=request_json,
            response_payload=response_json,
        )
        return replayable_response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "retryable": exc.retryable,
                "correlation_id": correlation_id,
                "severity": exc.severity or severity_from_status(exc.status_code),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
        details: dict = {}
        code = f"HTTP_{exc.status_code}"
        message = "Ошибка запроса"
        retryable = exc.status_code >= 500
        severity = severity_from_status(exc.status_code)
        if isinstance(exc.detail, dict):
            code = exc.detail.get("code", code)
            message = exc.detail.get("message", message)
            details = exc.detail.get("details", {})
            retryable = exc.detail.get("retryable", retryable)
            severity = exc.detail.get("severity", severity)
        elif isinstance(exc.detail, str):
            message = exc.detail
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": code,
                "message": message,
                "details": details,
                "retryable": retryable,
                "correlation_id": correlation_id,
                "severity": severity,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "code": "VALIDATION_ERROR",
                "message": "Некорректные параметры запроса",
                "details": {"errors": exc.errors()},
                "retryable": False,
                "correlation_id": correlation_id,
                "severity": "warning",
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, _: Exception):
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": "INTERNAL_ERROR",
                "message": "Внутренняя ошибка сервиса",
                "details": {},
                "retryable": True,
                "correlation_id": correlation_id,
                "severity": "error",
            },
        )

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
