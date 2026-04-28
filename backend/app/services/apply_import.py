from __future__ import annotations

from datetime import datetime
from hashlib import sha1
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models import Import, OperatorQueueItem, StatusHistory, TargetObject, TaskAssignment
from app.services.scheduling import next_action_for_new_assignment


def _assignment_external_key(project_id: str, target_object_external_key: str) -> str:
    raw = f"{project_id}:{target_object_external_key}:main"
    return sha1(raw.encode("utf-8")).hexdigest()


def _task_code() -> str:
    return f"T-{str(uuid4())[:8].upper()}"


def apply_import_to_domain(db: Session, imp: Import) -> dict[str, int]:
    if not imp.source_rows:
        return {"created_target_objects": 0, "updated_target_objects": 0, "created_assignments": 0, "updated_assignments": 0}

    created_t = 0
    updated_t = 0
    created_a = 0
    updated_a = 0
    seen_keys: set[str] = set()

    for row in imp.source_rows:
        key = (row.get("Ссылка на проект") or "").strip()
        if not key:
            continue
        seen_keys.add(key)
        name = (row.get("Проект") or "").strip() or key
        responsible = (row.get("РП") or "").strip()

        target = (
            db.query(TargetObject)
            .filter(
                TargetObject.project_id == imp.project_id,
                TargetObject.target_object_external_key == key,
            )
            .first()
        )
        if target is None:
            target = TargetObject(
                project_id=imp.project_id,
                target_object_external_key=key,
                target_object_name=name,
                responsible_person_ref=responsible,
                source_import_version=imp.import_version,
                source_payload_snapshot=row,
                last_seen_in_import_version=imp.import_version,
            )
            db.add(target)
            db.flush()
            created_t += 1
        else:
            changed = (
                target.target_object_name != name
                or (target.responsible_person_ref or "") != responsible
                or target.last_seen_in_import_version != imp.import_version
            )
            target.target_object_name = name
            target.responsible_person_ref = responsible
            target.source_import_version = imp.import_version
            target.source_payload_snapshot = row
            target.last_seen_in_import_version = imp.import_version
            target.updated_at = datetime.utcnow()
            if changed:
                updated_t += 1

        external_key = _assignment_external_key(imp.project_id, key)
        assignment = db.query(TaskAssignment).filter(TaskAssignment.external_key == external_key).first()
        if assignment is None:
            assignment = TaskAssignment(
                external_key=external_key,
                project_id=imp.project_id,
                target_object_id=target.id,
                task_code=_task_code(),
                title=f"Контроль: {name}",
                status="new",
                next_action_at=next_action_for_new_assignment(),
                progress_completion=0,
            )
            db.add(assignment)
            db.flush()
            db.add(
                StatusHistory(
                    assignment_id=assignment.id,
                    from_status=None,
                    to_status="new",
                    reason="import_apply_create",
                    actor_id=imp.imported_by,
                )
            )
            created_a += 1
        else:
            assignment.target_object_id = target.id
            assignment.title = f"Контроль: {name}"
            assignment.assignee_person_id = responsible or assignment.assignee_person_id
            assignment.updated_at = datetime.utcnow()
            assignment.revision += 1
            updated_a += 1

    missing_in_new_import = (
        db.query(TargetObject)
        .filter(TargetObject.project_id == imp.project_id)
        .all()
    )
    for target in missing_in_new_import:
        if target.target_object_external_key in seen_keys:
            continue
        db.add(
            OperatorQueueItem(
                assignment_id=None,
                type="import_warning",
                reason="target_object_missing_in_new_import",
                payload={
                    "target_object_external_key": target.target_object_external_key,
                    "project_id": imp.project_id,
                    "import_version": imp.import_version,
                },
                status="new",
            )
        )

    return {
        "created_target_objects": created_t,
        "updated_target_objects": updated_t,
        "created_assignments": created_a,
        "updated_assignments": updated_a,
    }
