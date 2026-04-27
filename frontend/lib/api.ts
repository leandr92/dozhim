const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";
const TOKEN = process.env.NEXT_PUBLIC_BEARER_TOKEN ?? "dev-token";

type FetchOptions = {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
};

export type ApiErrorPayload = {
  code: string;
  message: string;
  details: Record<string, unknown>;
  retryable: boolean;
  correlation_id: string;
  severity: "info" | "warning" | "error";
};

export class ApiError extends Error {
  status: number;
  payload: ApiErrorPayload;

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message);
    this.status = status;
    this.payload = payload;
  }
}

export function getErrorText(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    const cid = error.payload.correlation_id ? ` [${error.payload.correlation_id}]` : "";
    return `${error.payload.message}${cid}`;
  }
  if (error instanceof Error) return error.message;
  return fallback;
}

async function request<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? "GET",
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      ...options.headers
    },
    body: options.body,
    cache: "no-store"
  });
  if (!res.ok) {
    let payload: ApiErrorPayload = {
      code: `HTTP_${res.status}`,
      message: `API error ${res.status}`,
      details: {},
      retryable: res.status >= 500,
      correlation_id: "n/a",
      severity: res.status >= 500 ? "error" : "warning"
    };
    try {
      const json = (await res.json()) as Partial<ApiErrorPayload>;
      payload = {
        ...payload,
        ...json,
        details: json.details ?? {}
      };
    } catch {
      // fallback keeps default payload
    }
    throw new ApiError(res.status, payload);
  }
  return (await res.json()) as T;
}

export type Assignment = {
  id: string;
  title: string;
  status: string;
  project_id: string;
  target_object_id: string;
  revision: number;
  deadline_at: string | null;
};

export type JobsResponse = {
  items: Array<{
    id: string;
    kind: string;
    status: string;
    retry_count: number;
    error: { message?: string; correlation_id?: string } | null;
    created_at: string;
  }>;
  page: number;
  page_size: number;
  total: number;
};

export type Campaign = {
  id: string;
  name: string;
  status: string;
  project_id: string;
  import_id: string | null;
  created_at: string;
};

export type CampaignsResponse = {
  items: Campaign[];
  page: number;
  page_size: number;
  total: number;
};

export type CampaignMessagesResponse = {
  campaign: {
    id: string;
    name: string;
    status: string;
    project_id: string;
    import_id: string | null;
  };
  counters: {
    ready: number;
    sent: number;
    blocked: number;
    review_required: number;
  };
  items: Array<{
    id: string;
    to_email: string;
    cc_emails: string[];
    subject: string;
    body: string;
    status: string;
    is_payload_immutable: boolean;
    email_sent_flag: boolean;
    manual_fallback_comment: string | null;
    revision: number;
  }>;
};

export type OperatorQueueItem = {
  id: string;
  assignment_id: string | null;
  type: string;
  reason: string | null;
  status: string;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type OperatorQueueResponse = {
  items: OperatorQueueItem[];
  page: number;
  page_size: number;
  total: number;
};

export type AssignmentsResponse = {
  items: Assignment[];
  page: number;
  page_size: number;
  total: number;
};

export type AssignmentDetailsResponse = {
  assignment: {
    id: string;
    task_code: string;
    title: string;
    status: string;
    project_id: string;
    target_object_id: string;
    deadline_at: string | null;
    progress_completion: number;
    progress_note: string | null;
    next_commitment_date: string | null;
    revision: number;
    created_at: string;
    updated_at: string;
  };
  allowed_actions: string[];
  status_history: Array<{
    id: string;
    from_status: string | null;
    to_status: string;
    reason: string | null;
    actor_id: string | null;
    created_at: string;
  }>;
  evidence: Array<{
    id: string;
    verification_status: string;
    business_outcome: string | null;
    technical_error_code: string | null;
    payload?: Record<string, unknown> | null;
    created_at: string;
  }>;
  revisions: Array<{
    id: string;
    revision: number;
    diff: Record<string, unknown>;
    actor_id: string | null;
    created_at: string;
  }>;
  touchpoints: Array<{
    id: string;
    channel: string;
    kind: string;
    payload: Record<string, unknown> | null;
    actor_id: string | null;
    created_at: string;
  }>;
};

export async function fetchAssignments(params?: {
  page?: number;
  page_size?: number;
  project_id?: string;
  target_object_id?: string;
  status_filter?: string;
  sort_by?: "created_at" | "deadline_at";
  sort_dir?: "asc" | "desc";
}): Promise<AssignmentsResponse> {
  const search = new URLSearchParams();
  if (params?.page) search.set("page", String(params.page));
  if (params?.page_size) search.set("page_size", String(params.page_size));
  if (params?.project_id) search.set("project_id", params.project_id);
  if (params?.target_object_id) search.set("target_object_id", params.target_object_id);
  if (params?.status_filter) search.set("status_filter", params.status_filter);
  if (params?.sort_by) search.set("sort_by", params.sort_by);
  if (params?.sort_dir) search.set("sort_dir", params.sort_dir);
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return request<AssignmentsResponse>(`/assignments${suffix}`);
}

export async function createAssignment(body: {
  project_id: string;
  title: string;
  target_object_external_key: string;
  target_object_name?: string;
  deadline_at?: string | null;
}) {
  return request<{ id: string; task_code: string; created: boolean }>("/assignments", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `create-assignment-${Date.now()}`
    },
    body: JSON.stringify(body)
  });
}

export async function deleteAssignment(assignmentId: string) {
  return request<{ id: string; deleted: boolean }>(`/assignments/${assignmentId}`, {
    method: "DELETE",
    headers: {
      "Idempotency-Key": `delete-assignment-${assignmentId}-${Date.now()}`
    }
  });
}

export async function fetchAssignmentDetails(assignmentId: string): Promise<AssignmentDetailsResponse> {
  return request<AssignmentDetailsResponse>(`/assignments/${assignmentId}`);
}

export async function patchAssignment(
  assignmentId: string,
  body: {
    revision: number;
    status?: string;
    deadline_at?: string | null;
    progress_completion?: number;
    progress_note?: string;
    next_commitment_date?: string | null;
  }
) {
  return request(`/assignments/${assignmentId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `patch-${assignmentId}-${Date.now()}`
    },
    body: JSON.stringify(body)
  });
}

export async function revertAssignment(assignmentId: string, revision: number) {
  return request<{ assignment_id: string; reverted: boolean; revision: number }>(`/assignments/${assignmentId}/revert`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `revert-${assignmentId}-${Date.now()}`
    },
    body: JSON.stringify({ revision })
  });
}

export async function runAssignmentAction(
  assignmentId: string,
  revision: number,
  action: string,
  payload: Record<string, unknown> = {}
) {
  return request(`/assignments/${assignmentId}/actions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `action-${assignmentId}-${Date.now()}`
    },
    body: JSON.stringify({ action, revision, payload })
  });
}

export async function fetchJobs(): Promise<JobsResponse> {
  return request<JobsResponse>("/jobs");
}

export async function retryJob(jobId: string) {
  return request(`/jobs/${jobId}/retry`, {
    method: "POST",
    headers: {
      "Idempotency-Key": `retry-job-${jobId}-${Date.now()}`
    }
  });
}

export async function fetchHealth(): Promise<{ status: string }> {
  return request<{ status: string }>("/health");
}

export async function fetchCampaigns(): Promise<CampaignsResponse> {
  return request<CampaignsResponse>("/campaigns");
}

export async function fetchCampaignMessages(campaignId: string): Promise<CampaignMessagesResponse> {
  return request<CampaignMessagesResponse>(`/campaigns/${campaignId}/messages`);
}

export async function patchCampaignMessage(
  campaignId: string,
  messageId: string,
  body: { subject: string; body: string; to_email: string; cc_emails: string[] }
) {
  return request(`/campaigns/${campaignId}/messages/${messageId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `msg-${messageId}-${Date.now()}`
    },
    body: JSON.stringify(body)
  });
}

export async function approveSendCampaign(campaignId: string) {
  return request(`/campaigns/${campaignId}/approve-send`, {
    method: "POST",
    headers: {
      "Idempotency-Key": `approve-${campaignId}-${Date.now()}`
    }
  });
}

export async function retryFailedCampaign(campaignId: string) {
  return request(`/campaigns/${campaignId}/retry-failed`, {
    method: "POST",
    headers: {
      "Idempotency-Key": `retry-${campaignId}-${Date.now()}`
    }
  });
}

export async function setManualSentFlag(campaignId: string, messageId: string, comment: string) {
  return request(`/campaigns/${campaignId}/messages/${messageId}/manual-sent-flag`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `manual-sent-${messageId}-${Date.now()}`
    },
    body: JSON.stringify({ comment })
  });
}

export async function fetchOperatorQueue(): Promise<OperatorQueueResponse> {
  return request<OperatorQueueResponse>("/operator-queue");
}

export async function claimQueueItem(itemId: string) {
  return request(`/operator-queue/${itemId}/claim`, {
    method: "POST",
    headers: {
      "Idempotency-Key": `claim-${itemId}-${Date.now()}`
    }
  });
}

export async function resolveQueueItem(itemId: string) {
  return request(`/operator-queue/${itemId}/resolve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `resolve-${itemId}-${Date.now()}`
    },
    body: JSON.stringify({ result: "done" })
  });
}

export async function followUpQueueItem(itemId: string) {
  return request(`/operator-queue/${itemId}/follow-up`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `followup-${itemId}-${Date.now()}`
    },
    body: JSON.stringify({ reason: "follow-up" })
  });
}

export async function bindQueueItemToAssignment(itemId: string, assignmentId: string) {
  return request(`/operator-queue/${itemId}/bind-assignment`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `bind-${itemId}-${Date.now()}`
    },
    body: JSON.stringify({ assignment_id: assignmentId })
  });
}

export type ProjectItem = {
  id: string;
  project_code: string;
  project_name: string;
  status: string;
  target_date?: string | null;
  created_at?: string;
};

export type ProjectsResponse = {
  items: ProjectItem[];
  page: number;
  page_size: number;
  total: number;
};

export async function fetchProjects(): Promise<ProjectsResponse> {
  return request<ProjectsResponse>("/projects");
}

export async function createProject(payload: {
  project_code: string;
  project_name: string;
  status?: string;
}) {
  return request<{ id: string; project_code: string }>("/projects", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `project-create-${Date.now()}`
    },
    body: JSON.stringify(payload)
  });
}

export async function patchProject(projectId: string, payload: { project_name?: string; status?: string }) {
  return request<{ id: string; updated: boolean }>(`/projects/${projectId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `project-patch-${projectId}-${Date.now()}`
    },
    body: JSON.stringify(payload)
  });
}

export type SettingsResponse = {
  quiet_days: string[];
  timezone: string;
  queue_red_zone: number;
};

export async function fetchSettings(): Promise<SettingsResponse> {
  return request<SettingsResponse>("/settings");
}

export async function saveSettings(payload: Partial<SettingsResponse>) {
  return request<{ updated: boolean; settings: SettingsResponse }>("/settings", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `settings-${Date.now()}`
    },
    body: JSON.stringify(payload)
  });
}

export type PersonItem = {
  id: string;
  full_name: string;
  email: string;
  telegram_user_id: string | null;
  phone: string;
  role: string;
  manager_person_id: string | null;
  is_active: boolean;
};

export type PeopleResponse = {
  items: PersonItem[];
  page: number;
  page_size: number;
  total: number;
};

export async function fetchPeople(): Promise<PeopleResponse> {
  return request<PeopleResponse>("/people");
}

export async function createPerson(payload: {
  full_name: string;
  email: string;
  telegram_user_id?: string;
  phone: string;
  role?: string;
  manager_person_id?: string;
}) {
  return request<{ id: string; created: boolean }>("/people", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `person-create-${Date.now()}`
    },
    body: JSON.stringify(payload)
  });
}

export async function patchPerson(
  personId: string,
  payload: Partial<{
    full_name: string;
    email: string;
    telegram_user_id: string;
    phone: string;
    role: string;
    manager_person_id: string | null;
    is_active: boolean;
  }>
) {
  return request<{ id: string; updated: boolean }>(`/people/${personId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `person-patch-${personId}-${Date.now()}`
    },
    body: JSON.stringify(payload)
  });
}

export type TemplateItem = {
  id: string;
  name: string;
  title_template: string;
  description: string | null;
  default_deadline_days: number;
  verification_policy: Record<string, unknown>;
  escalation_policy: Record<string, unknown>;
  calendar_policy: Record<string, unknown>;
  status: string;
};

export type TemplatesResponse = {
  items: TemplateItem[];
  page: number;
  page_size: number;
  total: number;
};

export async function fetchTemplates(): Promise<TemplatesResponse> {
  return request<TemplatesResponse>("/templates");
}

export async function createTemplate(payload: {
  name: string;
  title_template: string;
  description?: string;
  default_deadline_days?: number;
  verification_policy?: Record<string, unknown>;
  escalation_policy?: Record<string, unknown>;
  calendar_policy?: Record<string, unknown>;
}) {
  return request<{ id: string; created: boolean }>("/templates", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `template-create-${Date.now()}`
    },
    body: JSON.stringify(payload)
  });
}

export async function patchTemplate(
  templateId: string,
  payload: Partial<{
    name: string;
    title_template: string;
    description: string;
    default_deadline_days: number;
    verification_policy: Record<string, unknown>;
    escalation_policy: Record<string, unknown>;
    calendar_policy: Record<string, unknown>;
    status: string;
  }>
) {
  return request<{ id: string; updated: boolean }>(`/templates/${templateId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `template-patch-${templateId}-${Date.now()}`
    },
    body: JSON.stringify(payload)
  });
}

export type BatchResponse = {
  id: string;
  project_id: string;
  template_id: string | null;
  name: string;
  status: string;
  result: Record<string, unknown> | null;
  error: Record<string, unknown> | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export async function createBatch(payload: {
  project_id: string;
  template_id?: string;
  name: string;
  people_ids?: string[];
}) {
  return request<{ id: string; status: string }>("/batches", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `batch-create-${Date.now()}`
    },
    body: JSON.stringify(payload)
  });
}

export async function fetchBatch(batchId: string): Promise<BatchResponse> {
  return request<BatchResponse>(`/batches/${batchId}`);
}

export async function retryBatch(batchId: string) {
  return request<{ id: string; status: string; result: Record<string, unknown> }>(`/batches/${batchId}/retry`, {
    method: "POST",
    headers: {
      "Idempotency-Key": `batch-retry-${batchId}-${Date.now()}`
    }
  });
}

export type KpiResponse = {
  totals: {
    assignments: number;
    done: number;
    cannot_be_done: number;
    overdue: number;
  };
  kpi: {
    outcome_ratio: number;
    outcome_percent: number;
  };
};

export async function fetchKpi(): Promise<KpiResponse> {
  return request<KpiResponse>("/metrics/kpi");
}

export type AuditLogItem = {
  id: string;
  actor_id: string | null;
  actor_role: string | null;
  action: string;
  method: string;
  path: string;
  status_code: number;
  correlation_id: string | null;
  diff: Record<string, unknown>;
  created_at: string;
};

export type AuditLogsResponse = {
  items: AuditLogItem[];
  page: number;
  page_size: number;
  total: number;
};

export type AuditLogsFilters = {
  page?: number;
  page_size?: number;
  sort_by?: "created_at" | "status_code";
  sort_dir?: "asc" | "desc";
  actor_id?: string;
  method?: string;
  path?: string;
  status_code?: number;
  from_ts?: string;
  to_ts?: string;
};

export async function fetchAuditLogs(filters: AuditLogsFilters = {}): Promise<AuditLogsResponse> {
  const params = new URLSearchParams();
  if (typeof filters.page === "number" && Number.isFinite(filters.page)) params.set("page", String(filters.page));
  if (typeof filters.page_size === "number" && Number.isFinite(filters.page_size)) params.set("page_size", String(filters.page_size));
  if (filters.sort_by) params.set("sort_by", filters.sort_by);
  if (filters.sort_dir) params.set("sort_dir", filters.sort_dir);
  if (filters.actor_id) params.set("actor_id", filters.actor_id);
  if (filters.method) params.set("method", filters.method);
  if (filters.path) params.set("path", filters.path);
  if (typeof filters.status_code === "number" && Number.isFinite(filters.status_code)) {
    params.set("status_code", String(filters.status_code));
  }
  if (filters.from_ts) params.set("from_ts", filters.from_ts);
  if (filters.to_ts) params.set("to_ts", filters.to_ts);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<AuditLogsResponse>(`/audit-logs${suffix}`);
}
