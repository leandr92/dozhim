from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ParsedInboundCommand:
    command: str
    task_code: str
    payload: dict


def parse_inbound_text(raw_text: str) -> ParsedInboundCommand | None:
    text = (raw_text or "").strip()
    if not text:
        return None
    parts = text.split()
    if len(parts) < 2:
        return None

    command = parts[0].upper()
    task_code = parts[1].upper()
    if not task_code.startswith("T-"):
        return None

    if command == "OK":
        return ParsedInboundCommand(command="OK", task_code=task_code, payload={})
    if command == "DONE":
        return ParsedInboundCommand(command="DONE", task_code=task_code, payload={})
    if command == "BLOCK":
        return ParsedInboundCommand(
            command="BLOCK",
            task_code=task_code,
            payload={"reason": " ".join(parts[2:]).strip() or "blocked_by_assignee"},
        )
    if command == "CALL":
        return ParsedInboundCommand(command="CALL", task_code=task_code, payload={})
    if command == "DATE" and len(parts) >= 3:
        promised_date = parts[2]
        return ParsedInboundCommand(
            command="DATE",
            task_code=task_code,
            payload={"next_commitment_date_raw": promised_date},
        )
    return None


def map_command_to_status(command: ParsedInboundCommand, current_status: str) -> tuple[str, dict]:
    if command.command == "OK":
        next_status = "acknowledged" if current_status in {"new", "notified", "overdue"} else current_status
        return next_status, {"source": "inbound", "command": command.command}
    if command.command == "DONE":
        return "done_pending_check", {"source": "inbound", "command": command.command}
    if command.command == "BLOCK":
        return "blocked", {"source": "inbound", "command": command.command, **command.payload}
    if command.command == "CALL":
        return "escalated", {"source": "inbound", "command": command.command, "manual_contact_requested": True}
    if command.command == "DATE":
        payload = {"source": "inbound", "command": command.command}
        value = command.payload.get("next_commitment_date_raw")
        try:
            payload["next_commitment_date"] = datetime.strptime(str(value), "%d.%m").replace(year=datetime.utcnow().year).date().isoformat()
        except ValueError:
            payload["next_commitment_date"] = None
        return "in_progress", payload
    return current_status, {"source": "inbound", "command": "UNKNOWN"}
