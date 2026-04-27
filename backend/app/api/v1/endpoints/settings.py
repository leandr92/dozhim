from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import require_bearer_token, require_roles
from app.db.models import AppSetting
from app.db.session import get_db

router = APIRouter(prefix="/settings", tags=["settings"])


DEFAULT_SETTINGS = {
    "quiet_days": ["saturday", "sunday"],
    "timezone": "Europe/Moscow",
    "queue_red_zone": 30,
}


@router.get("")
def get_settings(
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(AppSetting, "global")
    if row is None:
        return DEFAULT_SETTINGS
    return row.value


@router.patch("")
def patch_settings(
    payload: dict,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    row = db.get(AppSetting, "global")
    if row is None:
        row = AppSetting(key="global", value={**DEFAULT_SETTINGS, **payload})
    else:
        row.value = {**row.value, **payload}
        row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    return {"updated": True, "settings": row.value}
