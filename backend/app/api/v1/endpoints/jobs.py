from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps.auth import require_bearer_token, require_roles
from app.db.models import Job
from app.db.session import get_db
from app.schemas.common import JobAccepted
from app.services.job_runner import run_once_with_summary
from app.services.jobs import new_job_id as generate_job_id

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(
    page: int = 1,
    page_size: int = 50,
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Job)
    total = query.count()
    rows = query.order_by(Job.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": row.id,
                "kind": row.kind,
                "status": row.status,
                "retry_count": row.retry_count,
                "last_retry_at": row.last_retry_at,
                "error": row.error,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/{job_id}")
def get_job(
    job_id: str,
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "payload": job.payload,
        "result": job.result,
        "error": job.error,
        "correlation_id": (job.error or {}).get("correlation_id"),
        "retry_count": job.retry_count,
        "last_retry_at": job.last_retry_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


@router.post("/{job_id}/cancel", status_code=status.HTTP_202_ACCEPTED, response_model=JobAccepted)
def cancel_job(
    job_id: str,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> JobAccepted:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    job.status = "cancelled"
    job.finished_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()
    db.add(job)

    cancel_job_id = generate_job_id()
    db.add(
        Job(
            id=cancel_job_id,
            kind="compensation_rollback",
            status="queued",
            payload={"source_job_id": job_id},
        )
    )
    db.commit()
    response.headers["Location"] = f"/api/v1/jobs/{cancel_job_id}"
    return JobAccepted(job_id=cancel_job_id)


@router.post("/run-once")
def run_one_job(
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
) -> dict:
    return run_once_with_summary()


@router.post("/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED, response_model=JobAccepted)
def retry_job(
    job_id: str,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> JobAccepted:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    source_job = db.get(Job, job_id)
    if source_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if source_job.status not in {"failed", "timed_out", "cancelled"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Job is not retryable")

    new_job_id = generate_job_id()
    db.add(
        Job(
            id=new_job_id,
            kind=source_job.kind,
            status="queued",
            payload=source_job.payload,
            retry_count=0,
        )
    )
    db.commit()
    response.headers["Location"] = f"/api/v1/jobs/{new_job_id}"
    return JobAccepted(job_id=new_job_id)
