from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps.auth import require_bearer_token
from app.db.models import AuditLog
from app.db.session import get_db

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])
MAX_PAGE_SIZE = 200


@router.get("")
def list_audit_logs(
    page: int = 1,
    page_size: int = 50,
    actor_id: str | None = None,
    method: str | None = None,
    path: str | None = None,
    status_code: int | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    query = db.query(AuditLog)
    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)
    if method:
        query = query.filter(AuditLog.method == method.upper())
    if path:
        query = query.filter(AuditLog.path.ilike(f"%{path}%"))
    if status_code is not None:
        query = query.filter(AuditLog.status_code == status_code)
    if from_ts is not None:
        query = query.filter(AuditLog.created_at >= from_ts)
    if to_ts is not None:
        query = query.filter(AuditLog.created_at <= to_ts)
    sort_by_norm = sort_by.strip().lower()
    sort_dir_norm = sort_dir.strip().lower()
    if sort_by_norm not in {"created_at", "status_code"}:
        sort_by_norm = "created_at"
    if sort_dir_norm not in {"asc", "desc"}:
        sort_dir_norm = "desc"

    sort_column = AuditLog.created_at if sort_by_norm == "created_at" else AuditLog.status_code
    query = query.order_by(sort_column.asc() if sort_dir_norm == "asc" else sort_column.desc(), AuditLog.created_at.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": row.id,
                "actor_id": row.actor_id,
                "actor_role": row.actor_role,
                "action": row.action,
                "method": row.method,
                "path": row.path,
                "status_code": row.status_code,
                "correlation_id": row.correlation_id,
                "diff": row.diff,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }
