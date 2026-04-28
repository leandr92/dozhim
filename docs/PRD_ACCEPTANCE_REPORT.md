# PRD Acceptance Report (Current Iteration)

Date: 2026-04-28

Scope of this iteration:
- Worker-first PRD gap closure with actionable assignment handlers.
- Scheduler + inbound/email + digest foundation without mandatory n8n dependency.

## Delivered

1. Domain contours:
- People: `GET/POST/PATCH /people`
- Templates/Policies: `GET/POST/PATCH /templates`
- Batches: `POST /batches`, `GET /batches/{id}`, `POST /batches/{id}/retry`

2. Assignment lifecycle:
- Manual create/delete.
- Revert endpoint: `POST /assignments/{id}/revert`.
- Filters/sort/pagination in assignments list.
- Conflict UX actions in assignment details (`Reload latest`, `Retry save`).
- Touchpoints timeline in assignment details.

3. Jobs/scheduler/channels:
- Removed successful no-op for known `assignment_action:*` jobs and implemented real handlers.
- Added due scheduler based on `next_action_at` in worker `run_once`.
- Added `channel:email_send` path with SMTP or stub mode and touchpoint logging.
- Added `POST /inbound/email` endpoint with service token, task code parsing and status transitions.
- Added `digest:daily` job scheduling and delivery foundation.

4. Campaign/Jobs UX:
- Manual fallback + immutable message handling preserved.
- Visual separation for sent vs editable campaign messages.
- Jobs long-running and timed_out informational notifications.
- Added owner review queue creation for unknown campaign recipients.

5. Audit/timezone:
- Audit page stabilized and working.
- Date/time formatting in key screens (`jobs`, `audit`, assignment touchpoints timeline).

6. Data model/migrations:
- Added tables: `people`, `task_templates`, `touchpoints`.
- Extended `task_batches` with runtime result/error/timestamps.
- Added assignment meeting fields for FR-14 fallback tracking.
- Added Alembic revisions:
  - `20260427_0008_people_templates_batches.py`
  - `20260427_0009_touchpoints.py`
  - `20260428_0010_assignment_meeting_fields.py`

## Test Evidence

- Full backend suite: `36 passed`.
- Frontend route smoke (dev server):
  - `/people` -> 200
  - `/templates` -> 200
  - `/batches` -> 200
  - `/audit` -> 200

## PRD Checklist Snapshot (without external integrations)

- PASS (implemented in this iteration):
  - People/Templates/Batches primary CRUD/runtime contours.
  - Assignment list filtering/sorting/pagination baseline.
  - Revert revision action.
  - Unified error notifications and job retry pathways.
  - Audit screen availability and touchpoints visibility.

- PARTIAL:
  - Full n8n workflow orchestration remains optional/deferred in worker-first track.
  - Verification SQL/file modes are contract-level and still need real external runtime integrations.
  - Meeting scheduling is fallback-only (`meeting_manual`), no free-busy slot search yet.

- DEFERRED (by scope decision):
  - Real Telegram client API integration.
  - Exchange calendar free-busy + invite automation.
  - Full n8n orchestration workflows (can be added over stable API contracts).

