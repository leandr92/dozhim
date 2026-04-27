# dozhim

## Backend (FastAPI)

### Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

API base path: `http://127.0.0.1:8000/api/v1`

### Initial endpoints

- `GET /api/v1/health`
- `GET /api/v1/assignments`
- `POST /api/v1/assignments`
- `GET /api/v1/assignments/{assignment_id}`
- `DELETE /api/v1/assignments/{assignment_id}`
- `GET /api/v1/assignments/{assignment_id}/actions/allowed`
- `PATCH /api/v1/assignments/{assignment_id}`
- `POST /api/v1/assignments/{assignment_id}/actions` (job-based)
- `POST /api/v1/campaigns/personalized/upload` (job-based)
- `GET /api/v1/imports`
- `POST /api/v1/imports/{import_id}/apply` (job-based)
- `GET /api/v1/operator-queue`
- `POST /api/v1/operator-queue/{item_id}/claim`
- `POST /api/v1/operator-queue/{item_id}/resolve`
- `POST /api/v1/operator-queue/{item_id}/follow-up`
- `POST /api/v1/operator-queue/{item_id}/bind-assignment`
- `POST /api/v1/operator-queue/inbound-unmatched`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/cancel` (job-based)
- `POST /api/v1/jobs/{job_id}/retry` (job-based)
- `POST /api/v1/jobs/run-once` (dev worker tick)
- `POST /api/v1/campaigns/{campaign_id}/messages/{message_id}/manual-sent-flag`
- `GET /api/v1/audit-logs`

### Auth and mutation headers

- Protected endpoints require `Authorization: Bearer <token>`.
- Mutating endpoints require `Idempotency-Key` header.
- Idempotency responses are persisted for 24h (`DOZHIM_IDEMPOTENCY_TTL_HOURS`); repeated request with same key and same payload returns stored response, with different payload returns `409 IDEMPOTENCY_KEY_REUSED`.
- HTTP verification adapter allowlist is controlled by `DOZHIM_VERIFICATION_HTTP_ALLOWED_HOSTS` (comma-separated, default: `127.0.0.1,localhost`).
- HTTP verification allowed methods are configured with `DOZHIM_VERIFICATION_HTTP_ALLOWED_METHODS` (default: `GET,POST`), and timeout is capped by `DOZHIM_VERIFICATION_HTTP_MAX_TIMEOUT_SECONDS` (default: `10.0`).
- HTTP verification also supports business condition checks by response JSON path (`response_json_path`, e.g. `$.result.status`) and expected JSON value (`expected_json_value`).

### Database migrations

```bash
cd backend
alembic upgrade head
```

### Worker daemon (background loop)

```bash
cd backend
python run_worker.py --poll-interval 2 --health-port 8100
```

Worker health endpoint:

- `GET http://127.0.0.1:8100/health`

Run without health API:

```bash
cd backend
python run_worker.py --no-health-api
```

## Frontend (Next.js + MUI + React Query)

### Run locally

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Frontend URL: `http://127.0.0.1:3000`