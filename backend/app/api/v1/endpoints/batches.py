from datetime import datetime, timedelta
from hashlib import sha1

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import require_bearer_token, require_roles
from app.db.models import Person, Project, TargetObject, TaskAssignment, TaskBatch, TaskTemplate
from app.db.session import get_db
from app.schemas.batches import BatchCreate

router = APIRouter(prefix="/batches", tags=["batches"])


def _assignment_external_key(project_id: str, target_object_external_key: str, template_id: str | None, person_id: str) -> str:
    raw = f"{project_id}:{target_object_external_key}:{template_id or 'manual'}:{person_id}"
    return sha1(raw.encode("utf-8")).hexdigest()


def _run_batch_generation(db: Session, batch: TaskBatch, people: list[Person]) -> dict:
    created = 0
    updated = 0
    template = db.get(TaskTemplate, batch.template_id) if batch.template_id else None
    title_template = (template.title_template if template else "Обязательство для {person_name}") if template else "Обязательство для {person_name}"
    deadline_days = template.default_deadline_days if template else 7

    for person in people:
        external_ref = f"person:{person.id}"
        target = (
            db.query(TargetObject)
            .filter(TargetObject.project_id == batch.project_id, TargetObject.target_object_external_key == external_ref)
            .first()
        )
        if target is None:
            target = TargetObject(
                project_id=batch.project_id,
                target_object_external_key=external_ref,
                target_object_name=person.full_name,
                responsible_person_ref=person.email,
            )
            db.add(target)
            db.flush()
        external_key = _assignment_external_key(batch.project_id, external_ref, batch.template_id, person.id)
        assignment = db.query(TaskAssignment).filter(TaskAssignment.external_key == external_key).first()
        title = title_template.replace("{person_name}", person.full_name)
        if assignment is None:
            assignment = TaskAssignment(
                external_key=external_key,
                project_id=batch.project_id,
                target_object_id=target.id,
                template_id=batch.template_id,
                assignee_person_id=person.id,
                task_code=f"B-{batch.id[:4].upper()}-{person.id[:4].upper()}",
                title=title,
                status="new",
                deadline_at=datetime.utcnow() + timedelta(days=deadline_days),
                progress_completion=0,
            )
            db.add(assignment)
            created += 1
        else:
            assignment.title = title
            assignment.deadline_at = datetime.utcnow() + timedelta(days=deadline_days)
            assignment.updated_at = datetime.utcnow()
            assignment.revision += 1
            db.add(assignment)
            updated += 1

    return {"created_assignments": created, "updated_assignments": updated, "people_count": len(people)}


@router.post("")
def create_batch(
    payload: BatchCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    project = db.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if payload.template_id and db.get(TaskTemplate, payload.template_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    people_query = db.query(Person).filter(Person.is_active.is_(True))
    if payload.people_ids:
        people_query = people_query.filter(Person.id.in_(payload.people_ids))
    people = people_query.all()
    if not people:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No active people for batch")

    batch = TaskBatch(
        project_id=payload.project_id,
        template_id=payload.template_id,
        name=payload.name.strip(),
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(batch)
    db.flush()
    try:
        summary = _run_batch_generation(db, batch, people)
        batch.status = "succeeded"
        batch.result = summary
        batch.error = None
        batch.finished_at = datetime.utcnow()
        batch.updated_at = datetime.utcnow()
        db.add(batch)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        batch.status = "failed"
        batch.error = {"message": str(exc)}
        batch.finished_at = datetime.utcnow()
        batch.updated_at = datetime.utcnow()
        db.add(batch)
        db.commit()
    return {"id": batch.id, "status": batch.status}


@router.get("/{batch_id}")
def get_batch(
    batch_id: str,
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    batch = db.get(TaskBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return {
        "id": batch.id,
        "project_id": batch.project_id,
        "template_id": batch.template_id,
        "name": batch.name,
        "status": batch.status,
        "result": batch.result,
        "error": batch.error,
        "started_at": batch.started_at,
        "finished_at": batch.finished_at,
        "created_at": batch.created_at,
    }


@router.post("/{batch_id}/retry")
def retry_batch(
    batch_id: str,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    batch = db.get(TaskBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if batch.status not in {"failed", "cancelled", "succeeded"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Batch is not retryable")

    people = db.query(Person).filter(Person.is_active.is_(True)).all()
    if not people:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No active people for batch")
    batch.status = "running"
    batch.started_at = datetime.utcnow()
    db.add(batch)
    db.flush()
    summary = _run_batch_generation(db, batch, people)
    batch.status = "succeeded"
    batch.result = summary
    batch.error = None
    batch.finished_at = datetime.utcnow()
    batch.updated_at = datetime.utcnow()
    db.add(batch)
    db.commit()
    return {"id": batch.id, "status": batch.status, "result": summary}
