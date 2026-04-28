# PRD Gap Matrix (Updated 2026-04-28)

This matrix maps PRD requirements to current implementation status and tests.

Legend:
- PASS: implemented and test/UI evidence exists
- PARTIAL: partially implemented
- FAIL: not implemented

| PRD Area | Backend Contract | Frontend Screen | Tests | Status | Notes |
|---|---|---|---|---|---|
| FR-1 People | `GET/POST/PATCH /people` | `/people` | `test_people_templates_batches.py` | PASS | CRUD + manager link + role constraints present |
| FR-2 Templates/Policies | `GET/POST/PATCH /templates` + policy validation | `/templates` | `test_people_templates_batches.py` | PARTIAL | Structured policy schema added; richer UI editing still limited |
| FR-3 Batch Runs | `POST /batches`, retry/get runtime | `/batches` | `test_people_templates_batches.py` | PASS | Batch creation/retry is working |
| FR-4 Individual assignments | `/assignments` CRUD + actions + next_action scheduling | `/assignments`, `/assignments/[id]` | `test_assignments_manual_crud.py` + others | PARTIAL | Core exists, channels/escalations still phase-based |
| FR-7 Scheduler reminders | worker due scheduler by `next_action_at` + run-once | no explicit UX | `test_job_worker.py` | PARTIAL | Worker-first scheduler implemented, n8n dispatcher deferred |
| FR-8 Status transitions from responses | `/inbound/email` + assignment actions/state machine | assignment details action panel | `test_jobs_retry_and_allowed_actions.py` | PARTIAL | Email inbound parser exists; Telegram inbound pending |
| FR-9 Verification methods | `run_verification` + evidence + manual/http/sql/file/webhook modes | verification panel in assignment details | `test_assignment_verification_job.py` | PARTIAL | SQL/file are MVP stubs, not external runtime integrations |
| FR-10 Escalations | assignment action handlers + queue item creation | partial action buttons | partial | PARTIAL | Meeting automation deferred; `meeting_manual` implemented |
| FR-11 Call-task | operator queue endpoints | `/operator-queue` | `test_operator_queue.py` | PASS | Basic queue operations present |
| FR-12 Daily digest | `digest:daily` job scheduling + SMTP/stub send | missing dedicated page | pending | PARTIAL | Backend digest flow exists, UI/reporting can be improved |
| FR-13 Calendar rules | `quiet_days` + `holiday_dates` + scheduling service | `/settings` partial | `test_projects_settings_metrics.py` | PARTIAL | Workday window/holiday transfer implemented minimally |
| FR-14 Meeting scheduling | `schedule_meeting` -> `meeting_manual` queue fallback | missing | pending | PARTIAL | Free-busy and invite creation deferred |
| FR-15 Verification via SQL/API | HTTP live adapter + SQL mode contract | assignment verification panel | `test_assignment_verification_job.py` | PARTIAL | SQL mode still simulated payload check |
| FR-16 Verification via file | file mode contract + verification_manual queue on failures | assignment verification panel | `test_assignment_verification_job.py` | PARTIAL | Full ingestion workflow still pending |
| FR-17 Campaign preview/edit | campaigns + manual fallback + retry + owner review queue | `/campaigns`, `/campaigns/[id]/preview` | `test_campaign_preview_actions.py`, `test_e2e_campaign_send_flow.py` | PARTIAL | ownership review and warnings added; richer conflict UX pending |
| FR-18 Project context | projects/settings/metrics endpoints | `/projects`, dashboard KPI | `test_projects_settings_metrics.py` | PARTIAL | Projects CRUD not full in UI |
| Audit logs | `/audit-logs` exists | `/audit` (currently broken syntax previously seen) | `test_audit_logs.py` | PARTIAL | Needs UI stabilization and task/campaign timeline integration |
| Jobs contract | `/jobs`, `/jobs/{id}`, cancel/retry/run-once + real handlers | `/jobs` | `test_jobs_retry_and_allowed_actions.py`, `test_job_worker.py` | PASS | no-op fallback removed for known kinds |

## Immediate Closure Order

1. External channel integrations (Telegram MTProto, production Exchange adapters).
2. FR-14 automated meeting-slot finder and invite creation.
3. Full SQL/file verification runtime (not stubbed payload modes).
4. Frontend depth for policy editing and digest visualization.
5. Traceability report update after each release cut.
