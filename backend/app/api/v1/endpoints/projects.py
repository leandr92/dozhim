from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import require_bearer_token, require_roles
from app.db.models import Project
from app.db.session import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects(
    page: int = 1,
    page_size: int = 50,
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Project).order_by(Project.created_at.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": row.id,
                "project_code": row.project_code,
                "project_name": row.project_name,
                "status": row.status,
                "target_date": row.target_date,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.post("")
def create_project(
    payload: dict,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    code = (payload.get("project_code") or "").strip()
    name = (payload.get("project_name") or "").strip()
    if not code or not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="project_code and project_name are required")
    exists = db.query(Project).filter(Project.project_code == code).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project code already exists")
    project = Project(
        project_code=code,
        project_name=name,
        status=payload.get("status", "active"),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": project.id, "project_code": project.project_code}


@router.patch("/{project_id}")
def patch_project(
    project_id: str,
    payload: dict,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if "project_name" in payload:
        project.project_name = payload["project_name"]
    if "status" in payload:
        project.status = payload["status"]
    project.updated_at = datetime.utcnow()
    db.add(project)
    db.commit()
    return {"id": project.id, "updated": True}
