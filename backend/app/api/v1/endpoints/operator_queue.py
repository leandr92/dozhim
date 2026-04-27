from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import require_bearer_token, require_roles
from app.db.models import OperatorQueueItem, TaskAssignment
from app.db.session import get_db

router = APIRouter(prefix="/operator-queue", tags=["operator-queue"])


@router.get("")
def list_operator_queue(
    page: int = 1,
    page_size: int = 50,
    queue_type: str | None = None,
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(OperatorQueueItem).order_by(OperatorQueueItem.created_at.desc())
    if queue_type:
        query = query.filter(OperatorQueueItem.type == queue_type)
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": row.id,
                "assignment_id": row.assignment_id,
                "type": row.type,
                "reason": row.reason,
                "status": row.status,
                "payload": row.payload or {},
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.post("/{item_id}/claim")
def claim_operator_queue_item(
    item_id: str,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    item = db.get(OperatorQueueItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue item not found")
    item.status = "in_progress"
    item.updated_at = datetime.utcnow()
    db.add(item)
    db.commit()
    return {"id": item.id, "status": item.status}


@router.post("/{item_id}/resolve")
def resolve_operator_queue_item(
    item_id: str,
    payload: dict,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    item = db.get(OperatorQueueItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue item not found")
    item.status = "resolved"
    merged_payload = {**(item.payload or {}), **(payload or {})}
    item.payload = merged_payload
    item.updated_at = datetime.utcnow()
    db.add(item)
    db.commit()
    return {"id": item.id, "status": item.status}


@router.post("/{item_id}/follow-up")
def create_follow_up_for_queue_item(
    item_id: str,
    payload: dict,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    item = db.get(OperatorQueueItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue item not found")

    new_item = OperatorQueueItem(
        assignment_id=item.assignment_id,
        type=payload.get("type", item.type),
        reason=payload.get("reason", "follow-up"),
        payload=payload.get("payload", {}),
        status="new",
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return {"id": new_item.id, "status": new_item.status}


@router.post("/{item_id}/bind-assignment")
def bind_queue_item_to_assignment(
    item_id: str,
    payload: dict,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    assignment_id = payload.get("assignment_id")
    if not assignment_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="assignment_id is required")

    item = db.get(OperatorQueueItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue item not found")
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    item.assignment_id = assignment_id
    item.updated_at = datetime.utcnow()
    merged_payload = {**(item.payload or {}), "bound_assignment_id": assignment_id}
    item.payload = merged_payload
    db.add(item)
    db.commit()
    return {"id": item.id, "status": item.status, "assignment_id": item.assignment_id}


@router.post("/inbound-unmatched")
def create_inbound_unmatched(
    payload: dict,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")

    assignment_id = payload.get("assignment_id")
    if assignment_id:
        assignment = db.get(TaskAssignment, assignment_id)
        if assignment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    item = OperatorQueueItem(
        assignment_id=assignment_id,
        type="inbound_unmatched",
        reason=payload.get("reason", "no_assignment_match"),
        payload=payload,
        status="new",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "status": item.status}
