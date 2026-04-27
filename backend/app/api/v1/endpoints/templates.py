from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import require_bearer_token, require_roles
from app.db.models import TaskTemplate
from app.db.session import get_db
from app.schemas.templates import TemplateCreate, TemplatePatch

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("")
def list_templates(
    page: int = 1,
    page_size: int = 50,
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(TaskTemplate).order_by(TaskTemplate.created_at.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": row.id,
                "name": row.name,
                "title_template": row.title_template,
                "description": row.description,
                "default_deadline_days": row.default_deadline_days,
                "verification_policy": row.verification_policy,
                "escalation_policy": row.escalation_policy,
                "calendar_policy": row.calendar_policy,
                "status": row.status,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.post("")
def create_template(
    payload: TemplateCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    exists = db.query(TaskTemplate).filter(TaskTemplate.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Template name already exists")
    template = TaskTemplate(
        name=payload.name.strip(),
        title_template=payload.title_template.strip(),
        description=payload.description,
        default_deadline_days=payload.default_deadline_days,
        verification_policy=payload.verification_policy,
        escalation_policy=payload.escalation_policy,
        calendar_policy=payload.calendar_policy,
        status="active",
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return {"id": template.id, "created": True}


@router.patch("/{template_id}")
def patch_template(
    template_id: str,
    payload: TemplatePatch,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    template = db.get(TaskTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(template, field, value)
    template.updated_at = datetime.utcnow()
    db.add(template)
    db.commit()
    return {"id": template.id, "updated": True}
