-- MVP schema (PostgreSQL)
-- Time fields are UTC (timestamptz)

create table projects (
  id uuid primary key,
  project_code text not null unique,
  project_name text not null,
  owner_person_id uuid,
  status text not null check (status in ('active','paused','archived')),
  start_date date,
  target_date date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table target_objects (
  id uuid primary key,
  project_id uuid not null references projects(id),
  target_object_external_key text not null,
  target_object_name text not null,
  responsible_person_ref text,
  source_import_version text,
  source_payload_snapshot jsonb,
  last_seen_in_import_version text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (project_id, target_object_external_key)
);

create table task_assignments (
  id uuid primary key,
  external_key text not null unique,
  project_id uuid not null references projects(id),
  target_object_id uuid not null references target_objects(id),
  template_id uuid,
  assignee_person_id uuid,
  task_code text not null unique,
  title text not null,
  status text not null check (status in (
    'new','notified','acknowledged','in_progress','done_pending_check',
    'done','cannot_be_done','overdue','escalated','blocked','cancelled'
  )),
  escalation_level integer not null default 0,
  deadline_at timestamptz,
  next_action_at timestamptz,
  progress_completion integer not null default 0 check (progress_completion between 0 and 100),
  progress_note text,
  next_commitment_date date,
  revision integer not null default 1,
  locked_by text,
  locked_at timestamptz,
  lock_expires_at timestamptz,
  cannot_be_done_comment text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table status_history (
  id uuid primary key,
  assignment_id uuid not null references task_assignments(id),
  from_status text,
  to_status text not null,
  reason text,
  actor_id text,
  created_at timestamptz not null default now()
);

create table task_batches (
  id uuid primary key,
  project_id uuid not null references projects(id),
  template_id uuid,
  name text not null,
  status text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table campaigns (
  id uuid primary key,
  project_id uuid not null references projects(id),
  import_id uuid,
  name text not null,
  status text not null check (status in ('draft','ready_for_review','approved','sending','sent','failed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table campaign_messages (
  id uuid primary key,
  campaign_id uuid not null references campaigns(id),
  assignment_id uuid references task_assignments(id),
  to_email text,
  cc_emails text[],
  subject text,
  body text,
  attachments jsonb,
  status text not null,
  is_payload_immutable boolean not null default false,
  email_sent_flag boolean not null default false,
  revision integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table touchpoints (
  id uuid primary key,
  assignment_id uuid references task_assignments(id),
  channel text not null,
  direction text not null check (direction in ('inbound','outbound','system','manual')),
  type text not null,
  payload jsonb,
  created_at timestamptz not null default now()
);

create table evidence (
  id uuid primary key,
  assignment_id uuid not null references task_assignments(id),
  verification_status text not null,
  business_outcome text,
  technical_error_code text,
  payload jsonb,
  payload_expires_at timestamptz,
  created_at timestamptz not null default now()
);

create table operator_queue (
  id uuid primary key,
  assignment_id uuid references task_assignments(id),
  type text not null,
  reason text,
  payload jsonb,
  status text not null default 'new',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table jobs (
  id uuid primary key,
  kind text not null,
  status text not null check (status in ('queued','running','succeeded','failed','timed_out','cancelled')),
  payload jsonb,
  result jsonb,
  error jsonb,
  retry_count integer not null default 0,
  last_retry_at timestamptz,
  lease_until timestamptz,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table revisions (
  id uuid primary key,
  entity_type text not null,
  entity_id uuid not null,
  revision integer not null,
  diff jsonb not null,
  actor_id text,
  created_at timestamptz not null default now(),
  unique (entity_type, entity_id, revision)
);

create table imports (
  id uuid primary key,
  project_id uuid not null references projects(id),
  import_version text not null unique,
  imported_by text not null,
  imported_at timestamptz not null,
  status text not null check (status in ('draft','validated','applied','failed')),
  dry_run boolean not null default false,
  diff jsonb,
  errors jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_assignments_project_status on task_assignments(project_id, status);
create index idx_assignments_next_action on task_assignments(next_action_at);
create index idx_jobs_status on jobs(status);
create index idx_operator_queue_status on operator_queue(status, type);
