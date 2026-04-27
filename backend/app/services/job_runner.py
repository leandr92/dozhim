from __future__ import annotations

import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.job_worker import lease_next_job, process_job


def run_background_loop(poll_interval_seconds: int = 2, max_cycles: int | None = None) -> None:
    cycles = 0
    while True:
        with SessionLocal() as db:  # type: Session
            job = lease_next_job(db)
            if job is not None:
                process_job(db, job)
        cycles += 1
        if max_cycles is not None and cycles >= max_cycles:
            return
        time.sleep(poll_interval_seconds)


def run_once_with_summary() -> dict:
    with SessionLocal() as db:  # type: Session
        job = lease_next_job(db)
        if job is None:
            return {"processed": False, "message": "No available jobs"}
        updated = process_job(db, job)
        return {
            "processed": True,
            "job_id": updated.id,
            "status": updated.status,
            "processed_at": datetime.utcnow().isoformat(),
        }
