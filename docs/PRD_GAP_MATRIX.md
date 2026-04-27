# PRD Gap Matrix (Baseline)

This matrix maps PRD requirements to current implementation status and tests.

Legend:
- PASS: implemented and test/UI evidence exists
- PARTIAL: partially implemented
- FAIL: not implemented

| PRD Area | Backend Contract | Frontend Screen | Tests | Status | Notes |
|---|---|---|---|---|---|
| FR-1 People | missing | missing | missing | FAIL | No `people` endpoints/pages yet |
| FR-2 Templates/Policies | missing | missing | missing | FAIL | No `templates` / `policies` APIs |
| FR-3 Batch Runs | missing dedicated runtime endpoints | missing | missing | FAIL | `task_batches` model exists only |
| FR-4 Individual assignments | `/assignments` CRUD + actions | `/assignments`, `/assignments/[id]` | `test_assignments_manual_crud.py` + others | PARTIAL | Core exists; revert/conflict UX incomplete |
| FR-7 Scheduler reminders | local worker loop exists | no explicit UX | `test_job_worker.py` | PARTIAL | No n8n workflow integration |
| FR-8 Status transitions from responses | assignment actions + guard | assignment details action panel | `test_jobs_retry_and_allowed_actions.py` | PARTIAL | Inbound channel parsing incomplete |
| FR-9 Verification methods | minimal evidence/read fields | no verification UX | `test_assignment_verification_job.py` | PARTIAL | SQL/API/file verification UI missing |
| FR-10 Escalations | partial via actions/job kinds | partial action buttons | partial | PARTIAL | Meeting escalation flow missing |
| FR-11 Call-task | operator queue endpoints | `/operator-queue` | `test_operator_queue.py` | PASS | Basic queue operations present |
| FR-12 Daily digest | missing | missing | missing | FAIL | No digest API/workflow |
| FR-13 Calendar rules | `/settings` partial | `/settings` partial | `test_projects_settings_metrics.py` | PARTIAL | Holidays/working days logic missing |
| FR-14 Meeting scheduling | missing | missing | missing | FAIL | No slot search/schedule endpoints |
| FR-15 Verification via SQL/API | missing runtime contract | missing | missing | FAIL | Not implemented |
| FR-16 Verification via file | missing runtime contract | missing | missing | FAIL | Not implemented |
| FR-17 Campaign preview/edit | campaigns + manual fallback + retry | `/campaigns`, `/campaigns/[id]/preview` | `test_campaign_preview_actions.py`, `test_e2e_campaign_send_flow.py` | PARTIAL | review-required/ownership handling incomplete |
| FR-18 Project context | projects/settings/metrics endpoints | `/projects`, dashboard KPI | `test_projects_settings_metrics.py` | PARTIAL | Projects CRUD not full in UI |
| Audit logs | `/audit-logs` exists | `/audit` (currently broken syntax previously seen) | `test_audit_logs.py` | PARTIAL | Needs UI stabilization and task/campaign timeline integration |
| Jobs contract | `/jobs`, `/jobs/{id}`, cancel/retry/run-once | `/jobs` | `test_jobs_retry_and_allowed_actions.py`, `test_job_worker.py` | PARTIAL | long-running/timeout UX gaps remain |

## Immediate Closure Order

1. Backend domain gaps: People, Templates/Policies, Batches.
2. Frontend screens and API bindings for those domains.
3. Assignment/campaign/jobs checklist UX gaps.
4. Audit/touchpoints/timezone completion.
5. Full tests and acceptance report.
