from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import require_bearer_token, require_roles
from app.db.models import Person
from app.db.session import get_db
from app.schemas.people import PersonCreate, PersonPatch

router = APIRouter(prefix="/people", tags=["people"])


@router.get("")
def list_people(
    page: int = 1,
    page_size: int = 50,
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Person).order_by(Person.created_at.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": row.id,
                "full_name": row.full_name,
                "email": row.email,
                "telegram_user_id": row.telegram_user_id,
                "phone": row.phone,
                "role": row.role,
                "manager_person_id": row.manager_person_id,
                "is_active": row.is_active,
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
def create_person(
    payload: PersonCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    exists = db.query(Person).filter(Person.email == payload.email).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Person with this email already exists")
    if payload.manager_person_id:
        manager = db.get(Person, payload.manager_person_id)
        if manager is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manager not found")
    person = Person(
        full_name=payload.full_name.strip(),
        email=payload.email,
        telegram_user_id=payload.telegram_user_id,
        phone=payload.phone.strip(),
        role=payload.role.strip().lower(),
        manager_person_id=payload.manager_person_id,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return {"id": person.id, "created": True}


@router.patch("/{person_id}")
def patch_person(
    person_id: str,
    payload: PersonPatch,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    updates = payload.model_dump(exclude_unset=True)
    if "manager_person_id" in updates and updates["manager_person_id"]:
        manager = db.get(Person, updates["manager_person_id"])
        if manager is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manager not found")
    for field, value in updates.items():
        setattr(person, field, value)
    person.updated_at = datetime.utcnow()
    db.add(person)
    db.commit()
    return {"id": person.id, "updated": True}
