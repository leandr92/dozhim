from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps.auth import require_bearer_token
from app.db.models import TaskAssignment
from app.db.session import get_db

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/kpi")
def get_kpi(
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    all_assignments = db.query(TaskAssignment).count()
    done_count = db.query(TaskAssignment).filter(TaskAssignment.status == "done").count()
    cannot_count = db.query(TaskAssignment).filter(TaskAssignment.status == "cannot_be_done").count()
    overdue_count = db.query(TaskAssignment).filter(TaskAssignment.status == "overdue").count()
    outcome_ratio = ((done_count + cannot_count) / all_assignments) if all_assignments else 0.0
    return {
        "totals": {
            "assignments": all_assignments,
            "done": done_count,
            "cannot_be_done": cannot_count,
            "overdue": overdue_count,
        },
        "kpi": {
            "outcome_ratio": outcome_ratio,
            "outcome_percent": round(outcome_ratio * 100, 2),
        },
    }
