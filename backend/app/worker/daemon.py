from __future__ import annotations

import signal
import time
from datetime import datetime

from app.services.job_runner import run_once_with_summary
from app.worker.state import worker_state


def _signal_handler(signum: int, _frame) -> None:
    _ = signum
    worker_state.stop_event.set()


def setup_signal_handlers() -> None:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)


def run_daemon(*, poll_interval_seconds: int = 2) -> None:
    setup_signal_handlers()
    worker_state.running = True
    try:
        while not worker_state.stop_event.is_set():
            summary = run_once_with_summary()
            worker_state.ticks += 1
            worker_state.last_tick_at = datetime.utcnow()
            if summary.get("processed"):
                worker_state.processed_jobs += 1
                worker_state.last_job_id = summary.get("job_id")
            time.sleep(poll_interval_seconds)
    finally:
        worker_state.running = False
