from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps.auth import require_bearer_token, require_roles
from app.db.models import Import, Job
from app.db.session import get_db
from app.schemas.common import JobAccepted
from app.services.apply_import import apply_import_to_domain
from app.services.jobs import new_job_id as generate_job_id

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("")
def list_imports(
    page: int = 1,
    page_size: int = 50,
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Import).order_by(Import.created_at.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": row.id,
                "import_version": row.import_version,
                "status": row.status,
                "imported_by": row.imported_by,
                "imported_at": row.imported_at,
                "dry_run": row.dry_run,
                "diff": row.diff,
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.post("/{import_id}/apply", status_code=status.HTTP_202_ACCEPTED, response_model=JobAccepted)
def apply_import(
    import_id: str,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin", "viewer")),
    db: Session = Depends(get_db),
) -> JobAccepted:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    imp = db.get(Import, import_id)
    if imp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")
    if imp.status not in {"validated", "draft"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Import is not applicable")

    summary = apply_import_to_domain(db, imp)
    imp.status = "applied"
    imp.diff = {**(imp.diff or {}), **summary}
    imp.updated_at = datetime.utcnow()
    job_id = generate_job_id()
    db.add(imp)
    db.add(
        Job(
            id=job_id,
            kind="import_apply",
            status="queued",
            payload={"import_id": import_id, "summary": summary},
        )
    )
    db.commit()
    response.headers["Location"] = f"/api/v1/jobs/{job_id}"
    return JobAccepted(job_id=job_id)
