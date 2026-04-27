from collections.abc import Iterable

TERMINAL_STATUSES = {"done", "cannot_be_done", "cancelled"}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "new": {"notified", "overdue", "blocked", "cancelled", "cannot_be_done"},
    "notified": {"acknowledged", "in_progress", "done_pending_check", "overdue", "blocked", "cancelled", "cannot_be_done"},
    "acknowledged": {"in_progress", "done_pending_check", "overdue", "blocked", "cancelled", "cannot_be_done"},
    "in_progress": {"done_pending_check", "overdue", "blocked", "cancelled", "cannot_be_done"},
    "done_pending_check": {"done", "in_progress", "cancelled", "cannot_be_done"},
    "overdue": {"escalated", "blocked", "cancelled", "cannot_be_done"},
    "escalated": {"escalated", "blocked", "cancelled", "cannot_be_done"},
    "blocked": {"in_progress", "escalated", "cancelled", "cannot_be_done"},
    "done": set(),
    "cannot_be_done": set(),
    "cancelled": set(),
}


def can_transition(from_status: str, to_status: str) -> bool:
    if from_status == to_status:
        return from_status == "escalated"
    return to_status in ALLOWED_TRANSITIONS.get(from_status, set())


def assert_transition(from_status: str, to_status: str, *, policy_enabled: bool = True) -> None:
    if not can_transition(from_status, to_status):
        raise ValueError(f"Transition {from_status} -> {to_status} is not allowed")
    if from_status == "overdue" and to_status == "escalated" and not policy_enabled:
        raise ValueError("Escalation disabled by policy")


def terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def require_in_status(status: str, allowed: Iterable[str]) -> None:
    if status not in set(allowed):
        raise ValueError(f"Status {status} is not in allowed set")
