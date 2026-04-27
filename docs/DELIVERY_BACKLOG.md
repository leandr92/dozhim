# Delivery Backlog (Iteration 1)

Этот backlog синхронизирован с:

- `docs/PRD.md`
- `docs/UI_WIREFRAMES.md`
- `docs/contracts/*`

## Поток 1: Backend Core

### B1. Schema + migrations

- Scope:
  - создать таблицы из `docs/contracts/sql-ddl.sql`;
  - добавить индексы и ограничения.
- Depends on: none
- DoD:
  - миграции применяются на чистой БД;
  - уникальные ключи/foreign keys работают;
  - smoke insert/select/update тесты проходят.

### B2. Assignment state machine service

- Scope:
  - реализовать переходы из `docs/contracts/state-machine.yaml`;
  - optimistic lock (`revision`) + `409 CONFLICT_EDIT`;
  - manual override c audit.
- Depends on: B1
- DoD:
  - все допустимые переходы проходят;
  - недопустимые переходы возвращают валидируемую ошибку;
  - `status_history` заполняется на каждый переход.

### B3. Job engine + scheduler

- Scope:
  - job statuses (`queued/running/succeeded/failed/timed_out/cancelled`);
  - cancel endpoint + rollback compensation;
  - scheduler configurable + lease/visibility timeout + `SKIP LOCKED`;
  - retry policy fixed + jitter.
- Depends on: B1
- DoD:
  - job lifecycle стабилен под параллельной нагрузкой;
  - terminal states корректно фиксируются;
  - cancel/retry сценарии покрыты тестами.

### B4. Import pipeline (dry run + apply)

- Scope:
  - excel/csv ingestion;
  - atomic validation;
  - dry run diff (`create/update/no-change`);
  - import statuses (`draft/validated/applied/failed`);
  - rules для missing owner / disappeared object.
- Depends on: B1, B3
- DoD:
  - невалидный файл не меняет данные;
  - diff формируется корректно;
  - import metadata (`import_version/imported_at/imported_by`) сохраняется.

### B5. API v1

- Scope:
  - реализовать endpoints из `docs/contracts/openapi.yaml`;
  - idempotency key для всех mutating endpoint;
  - unified error contract.
- Depends on: B2, B3, B4
- DoD:
  - контрактные тесты OpenAPI green;
  - `202 + Location + job_id` на job-based операциях;
  - `Idempotency-Key` работает по правилам (TTL 24h, 409 mismatch payload).

## Поток 2: Frontend Shell

### F1. App shell + navigation

- Scope:
  - маршруты и sidebar из `UI_WIREFRAMES.md` (`Navigation Model`);
  - SSR + MUI + React Query setup.
- Depends on: B5 (минимум mock/stub API)
- DoD:
  - все базовые route доступны;
  - breadcrumbs работают;
  - query params сохраняют состояние фильтров.

### F2. Lists and details

- Scope:
  - `Dashboard`, `Assignments List`, `Assignment Details`;
  - default filters;
  - конфликт редактирования, lock banner, revert action.
- Depends on: F1, B5
- DoD:
  - CRUD/переходы стабильны;
  - `409 CONFLICT_EDIT` корректно обрабатывается;
  - `Retry` для `save failed` реализован.

### F3. Campaign Preview & Edit

- Scope:
  - draft list + preview + explicit save;
  - approve/send flow;
  - sent payload immutable.
- Depends on: F1, B4, B5
- DoD:
  - нет autosave;
  - counters `ready/sent/blocked/review_required` отображаются;
  - partial failed обрабатывается (`Retry failed`, `Экспорт ошибок`).

### F4. Jobs page + operator queue

- Scope:
  - jobs list/details + polling + cancel/retry;
  - operator queue tabs and actions.
- Depends on: F1, B3, B5
- DoD:
  - polling stops on terminal status;
  - long-running marker after 120s;
  - jobs history visible for 24h.

## Поток 3: QA + Observability

### Q1. Contract and integration tests

- Scope:
  - API contract tests;
  - state machine tests;
  - import validation scenarios.
- Depends on: B5
- DoD:
  - критичные happy-path + fail-path покрыты;
  - regression suite запускается в CI.

### Q2. Frontend acceptance suite

- Scope:
  - чеклист из PRD (`Frontend Acceptance Checklist`);
  - e2e smoke path.
- Depends on: F2, F3, F4
- DoD:
  - минимум 1 e2e сценарий полностью green;
  - все пункты с `MUST` статусом PASS.

### Q3. Metrics, logs, tracing

- Scope:
  - structured JSON logs;
  - correlation id propagation;
  - метрики: `import_fail_rate`, `job_timeout_rate`, `escalation_effectiveness`.
- Depends on: B3, B5
- DoD:
  - метрики доступны в дашборде мониторинга;
  - correlation id виден в API и job логах;
  - alerting пороги задокументированы.

## Рекомендованный порядок запуска

1. Backend: B1 -> B2/B3 -> B4 -> B5.
2. Frontend: F1 параллельно с B5 mock, затем F2/F3/F4.
3. QA/Obs: Q1/Q3 параллельно, Q2 после F2+F3+F4.

## Критерий готовности итерации

- Контракты и поведение API соответствуют `docs/contracts/*`.
- Wireframe-critical flows реализованы без блокирующих UX-дефектов.
- E2E пилотный сценарий проходит end-to-end.
