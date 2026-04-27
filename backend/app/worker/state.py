from datetime import datetime
from threading import Event


class WorkerState:
    def __init__(self) -> None:
        self.started_at = datetime.utcnow()
        self.last_tick_at: datetime | None = None
        self.last_job_id: str | None = None
        self.running = False
        self.stop_event = Event()
        self.ticks = 0
        self.processed_jobs = 0

    def as_dict(self) -> dict:
        return {
            "running": self.running,
            "started_at": self.started_at.isoformat(),
            "last_tick_at": self.last_tick_at.isoformat() if self.last_tick_at else None,
            "last_job_id": self.last_job_id,
            "ticks": self.ticks,
            "processed_jobs": self.processed_jobs,
        }


worker_state = WorkerState()
