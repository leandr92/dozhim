# UI -> API -> Job Mapping (MVP)

Единая матрица для frontend/backend/QA: каждый CTA обязан иметь endpoint, модель job-статусов и обработку ошибок.

## Dashboard

| CTA | Endpoint | Job-based | UI states | Error handling |
|---|---|---|---|---|
| Обновить данные | `GET /api/v1/assignments` | no | loading -> success | `Error` banner + retry |
| Открыть assignment | route to `/assignments/:id` | no | navigation | `404` -> not found screen |
| Перейти в очередь | route to `/operator-queue` | no | navigation | n/a |

## Assignments List

| CTA | Endpoint | Job-based | UI states | Error handling |
|---|---|---|---|---|
| Применить фильтры | `GET /api/v1/assignments?...` | no | loading -> success/empty | `Error` banner + retry |
| Сохранить представление | `POST /api/v1/views` | yes (`202`) | saving -> queued/running -> succeeded | `failed` -> retry; `409` -> show conflict |
| Открыть | route to `/assignments/:id` | no | navigation | n/a |

## Assignment Details

| CTA | Endpoint | Job-based | UI states | Error handling |
|---|---|---|---|---|
| Сохранить | `PATCH /api/v1/assignments/{id}` | no | saving -> success | `409 CONFLICT_EDIT` -> block save + `Reload latest` |
| Run verification now | `POST /api/v1/assignments/{id}/actions` | yes (`202`) | queued/running -> succeeded/failed/timed_out | failed -> `Retry`; timed_out -> open jobs |
| Send reminder | `POST /api/v1/assignments/{id}/actions` | yes (`202`) | queued/running -> succeeded/failed | `INTEGRATION_UNAVAILABLE` -> retry/manual fallback |
| Schedule meeting | `POST /api/v1/assignments/{id}/actions` | yes (`202`) | queued/running -> succeeded/failed | failed -> show reason + create `meeting_manual` |
| Revert to previous revision | `POST /api/v1/assignments/{id}/actions` | no | reverting -> success | failed -> retry |

## Campaign Preview & Edit

| CTA | Endpoint | Job-based | UI states | Error handling |
|---|---|---|---|---|
| Загрузить Excel/CSV | `POST /api/v1/campaigns/personalized/upload` | yes (`202`) | draft_generating -> ready_for_review | `422 IMPORT_VALIDATION_FAILED` + export errors |
| Save message | `PATCH /api/v1/campaigns/{id}/messages/{msgId}` | no | saving -> success | conflict -> reload latest; failed -> retry |
| Approve and Send | `POST /api/v1/campaigns/{id}/approve-send` | yes (`202`) | send_in_progress -> completed/partial_failed | partial -> `Retry failed` + export errors |
| Retry failed | `POST /api/v1/campaigns/{id}/retry-failed` | yes (`202`) | queued/running -> succeeded/failed | failed -> open jobs + correlation id |

## Operator Queue

| CTA | Endpoint | Job-based | UI states | Error handling |
|---|---|---|---|---|
| Взять в работу | `POST /api/v1/operator-queue/{id}/claim` | no | loading -> claimed | failed -> toast + retry |
| Завершить | `POST /api/v1/operator-queue/{id}/resolve` | no | resolving -> success | validation error -> inline |
| Создать follow-up | `POST /api/v1/operator-queue/{id}/follow-up` | yes (`202`) | queued/running -> succeeded/failed | failed -> retry/manual |

## Jobs page

| CTA | Endpoint | Job-based | UI states | Error handling |
|---|---|---|---|---|
| Обновить статус | `GET /api/v1/jobs/{id}` | no | loading -> success | failed -> retry |
| Retry | endpoint by context | yes (`202`) | queued/running -> terminal | failed -> correlation id + error details |
| Cancel job | `POST /api/v1/jobs/{id}/cancel` | yes (`202`) | cancelling -> cancelled | failed -> retry |

## Common job UI behavior

- Job warning threshold: 120 seconds (`operation is taking longer than usual`).
- Job history retention in UI: 24 hours.
- Polling should stop on terminal statuses: `succeeded`, `failed`, `timed_out`, `cancelled`.
- Use unified error contract:
  - `code`, `message`, `details`, `retryable`, `correlation_id`.
