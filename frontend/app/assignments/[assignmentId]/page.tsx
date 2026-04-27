"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Chip,
  Grid,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography
} from "@mui/material";
import { useMemo, useState } from "react";
import NotificationStack from "@/components/NotificationStack";

import { ApiError, fetchAssignmentDetails, patchAssignment, revertAssignment, runAssignmentAction } from "@/lib/api";
import { useMutationNotifications, useQueryNotifications } from "@/hooks/useNotifications";

type Props = { params: { assignmentId: string } };

export default function AssignmentDetailsPage({ params }: Props) {
  const id = params.assignmentId;
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["assignment", id], queryFn: () => fetchAssignmentDetails(id), refetchInterval: 7000 });

  const assignment = query.data?.assignment;
  const [progress, setProgress] = useState<number>(0);
  const [note, setNote] = useState<string>("");
  const [verificationMode, setVerificationMode] = useState<"manual" | "http_api" | "sql_query" | "file" | "webhook">("manual");
  const [manualStatus, setManualStatus] = useState("verified");
  const [manualOutcome, setManualOutcome] = useState("done");
  const [httpUrl, setHttpUrl] = useState("http://127.0.0.1:8000/api/v1/health");
  const [httpMethod, setHttpMethod] = useState("GET");
  const [httpExpectedStatus, setHttpExpectedStatus] = useState(200);
  const [httpTimeoutSeconds, setHttpTimeoutSeconds] = useState(5);
  const [httpRetries, setHttpRetries] = useState(3);
  const [httpResponseJsonPath, setHttpResponseJsonPath] = useState("$.result.status");
  const [httpExpectedJsonValueRaw, setHttpExpectedJsonValueRaw] = useState('"ok"');
  const [httpHeadersJson, setHttpHeadersJson] = useState("{}");
  const [httpBodyJson, setHttpBodyJson] = useState("{}");
  const [httpPreviewResponseJson, setHttpPreviewResponseJson] = useState('{"result":{"status":"ok"}}');
  const [httpJsonHelperMessage, setHttpJsonHelperMessage] = useState<string>("");
  const [httpJsonHelperError, setHttpJsonHelperError] = useState(false);
  const [httpPreviewMessage, setHttpPreviewMessage] = useState<string>("");
  const [httpPreviewError, setHttpPreviewError] = useState(false);
  const [sqlRowCount, setSqlRowCount] = useState(1);
  const [sqlMinRequired, setSqlMinRequired] = useState(1);
  const [fileExists, setFileExists] = useState("true");
  const [webhookReceived, setWebhookReceived] = useState("true");
  const [lastSavePayload, setLastSavePayload] = useState<{ progress_completion: number; progress_note: string } | null>(null);
  const revision = useMemo(() => assignment?.revision ?? 1, [assignment?.revision]);
  const formatDate = (value: string | null | undefined) =>
    value ? new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "medium" }).format(new Date(value)) : "-";

  const extractByJsonPath = (obj: unknown, path: string): unknown => {
    const normalized = path.trim();
    if (!normalized.startsWith("$.")) {
      throw new Error("response_json_path должен начинаться с '$.'");
    }
    const parts = normalized.slice(2).split(".").filter(Boolean);
    let current: unknown = obj;
    for (const part of parts) {
      if (!current || typeof current !== "object" || !(part in (current as Record<string, unknown>))) {
        throw new Error(`Путь '${normalized}' не найден в JSON`);
      }
      current = (current as Record<string, unknown>)[part];
    }
    return current;
  };

  const parseHttpJsonInputs = () => {
    let parsedHeaders: Record<string, string> = {};
    let parsedBody: Record<string, unknown> | undefined;
    const headersObj = JSON.parse(httpHeadersJson || "{}");
    if (headersObj && typeof headersObj === "object") {
      parsedHeaders = Object.fromEntries(
        Object.entries(headersObj as Record<string, unknown>).map(([k, v]) => [k, String(v)])
      );
    }
    const bodyObj = JSON.parse(httpBodyJson || "{}");
    if (bodyObj && typeof bodyObj === "object") {
      parsedBody = bodyObj as Record<string, unknown>;
    }
    let expectedJsonValue: unknown = undefined;
    if (httpResponseJsonPath.trim() && httpExpectedJsonValueRaw.trim()) {
      expectedJsonValue = JSON.parse(httpExpectedJsonValueRaw);
    }
    return { parsedHeaders, parsedBody, expectedJsonValue };
  };

  const validateHttpJson = () => {
    try {
      parseHttpJsonInputs();
      setHttpJsonHelperError(false);
      setHttpJsonHelperMessage("JSON валиден");
    } catch {
      setHttpJsonHelperError(true);
      setHttpJsonHelperMessage("Некорректный JSON в headers или body");
    }
  };

  const formatHttpJson = () => {
    try {
      setHttpHeadersJson(JSON.stringify(JSON.parse(httpHeadersJson || "{}"), null, 2));
      setHttpBodyJson(JSON.stringify(JSON.parse(httpBodyJson || "{}"), null, 2));
      if (httpExpectedJsonValueRaw.trim()) {
        setHttpExpectedJsonValueRaw(JSON.stringify(JSON.parse(httpExpectedJsonValueRaw), null, 2));
      }
      setHttpJsonHelperError(false);
      setHttpJsonHelperMessage("JSON отформатирован");
    } catch {
      setHttpJsonHelperError(true);
      setHttpJsonHelperMessage("Невозможно форматировать: некорректный JSON");
    }
  };

  const applyPathTemplate = (template: string) => {
    setHttpResponseJsonPath(template);
    setHttpPreviewError(false);
    setHttpPreviewMessage(`Шаблон применен: ${template}`);
  };

  const runHttpPreview = () => {
    try {
      const responseObj = JSON.parse(httpPreviewResponseJson);
      const actual = extractByJsonPath(responseObj, httpResponseJsonPath);
      const expected = httpExpectedJsonValueRaw.trim() ? JSON.parse(httpExpectedJsonValueRaw) : undefined;
      const matches = expected === undefined ? true : JSON.stringify(actual) === JSON.stringify(expected);
      setHttpPreviewError(!matches);
      setHttpPreviewMessage(
        matches
          ? `Preview OK: path value = ${JSON.stringify(actual)}`
          : `Preview mismatch: actual=${JSON.stringify(actual)}, expected=${JSON.stringify(expected)}`
      );
    } catch (err) {
      setHttpPreviewError(true);
      setHttpPreviewMessage(err instanceof Error ? err.message : "Ошибка preview");
    }
  };

  const useLastEvidencePayloadAsPreview = () => {
    const lastEvidence = query.data?.evidence?.[0];
    const payload = lastEvidence?.payload;
    if (!payload || typeof payload !== "object") {
      setHttpPreviewError(true);
      setHttpPreviewMessage("В последнем evidence нет payload для preview");
      return;
    }
    const payloadRecord = payload as Record<string, unknown>;
    const responseBody = payloadRecord.response_body;
    const previewSource =
      responseBody && typeof responseBody === "object"
        ? responseBody
        : payload;
    setHttpPreviewResponseJson(JSON.stringify(previewSource, null, 2));
    setHttpPreviewError(false);
    setHttpPreviewMessage(
      responseBody && typeof responseBody === "object"
        ? "Preview JSON обновлен из payload.response_body"
        : "Preview JSON обновлен из последнего evidence payload"
    );
  };

  const save = useMutation({
    mutationFn: () =>
      patchAssignment(id, {
        revision,
        progress_completion: progress,
        progress_note: note
      }),
    onSuccess: () => {
      setLastSavePayload({ progress_completion: progress, progress_note: note });
      qc.invalidateQueries({ queryKey: ["assignment", id] });
    }
  });
  const revert = useMutation({
    mutationFn: (targetRevision: number) => revertAssignment(id, targetRevision),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["assignment", id] })
  });

  const actionMutation = useMutation({
    mutationFn: (action: string) => {
      const payload =
        action === "run_verification"
          ? verificationMode === "manual"
            ? { mode: "manual", verification_status: manualStatus, business_outcome: manualOutcome }
            : verificationMode === "http_api"
              ? (() => {
                  try {
                    const { parsedHeaders, parsedBody, expectedJsonValue } = parseHttpJsonInputs();
                    setHttpJsonHelperError(false);
                    setHttpJsonHelperMessage("");
                    return {
                      mode: "http_api",
                      url: httpUrl,
                      method: httpMethod,
                      expected_status: httpExpectedStatus,
                      timeout_seconds: httpTimeoutSeconds,
                      retries: httpRetries,
                      response_json_path: httpResponseJsonPath.trim() || undefined,
                      expected_json_value: expectedJsonValue,
                      headers: parsedHeaders,
                      body: parsedBody,
                    };
                  } catch {
                    setHttpJsonHelperError(true);
                    setHttpJsonHelperMessage("Некорректный JSON в HTTP headers/body или expected_json_value");
                    throw new Error("Некорректный JSON в HTTP headers");
                  }
                })()
              : verificationMode === "sql_query"
                ? { mode: "sql_query", row_count: sqlRowCount, min_required: sqlMinRequired }
                : verificationMode === "file"
                  ? { mode: "file", file_exists: fileExists === "true" }
                  : { mode: "webhook", webhook_received: webhookReceived === "true" }
          : {};
      return runAssignmentAction(id, revision, action, payload);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["assignment", id] })
  });
  const queryNotifications = useQueryNotifications([
    { id: "assignment-load", error: query.error, fallback: "Не удалось загрузить карточку" },
  ]);
  const mutationNotifications = useMutationNotifications([
    {
      id: "assignment-action",
      error: save.error ?? actionMutation.error ?? revert.error ?? undefined,
      success: save.isSuccess || actionMutation.isSuccess || revert.isSuccess,
      errorFallback: "Не удалось выполнить действие",
      successMessage: "Изменения по задаче сохранены",
    },
  ]);
  const isConflictError = (save.error instanceof ApiError && save.error.payload.code === "HTTP_409") || (save.error instanceof ApiError && save.error.payload.code === "CONFLICT_EDIT");
  const notifications = [...queryNotifications, ...mutationNotifications];

  if (query.isLoading) return <Typography>Загрузка...</Typography>;
  if (query.isError || !assignment) return <NotificationStack items={notifications} />;

  return (
    <Stack spacing={2}>
      <Typography variant="h4">{assignment.title}</Typography>
      <Stack direction="row" spacing={1}>
        <Chip label={`Статус: ${assignment.status}`} />
        <Chip label={`Revision: ${assignment.revision}`} />
        <Chip label={`Task: ${assignment.task_code}`} />
      </Stack>
      <NotificationStack items={notifications} />
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          ActionPanel (allowed next actions)
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mb: 1 }}>
          <TextField
            select
            size="small"
            label="Verification mode"
            value={verificationMode}
            onChange={(e) => setVerificationMode(e.target.value as "manual" | "http_api" | "sql_query" | "file" | "webhook")}
            sx={{ minWidth: 180 }}
          >
            <MenuItem value="manual">manual</MenuItem>
            <MenuItem value="http_api">http_api</MenuItem>
            <MenuItem value="sql_query">sql_query</MenuItem>
            <MenuItem value="file">file</MenuItem>
            <MenuItem value="webhook">webhook</MenuItem>
          </TextField>
          {verificationMode === "manual" && (
            <>
              <TextField size="small" label="verification_status" value={manualStatus} onChange={(e) => setManualStatus(e.target.value)} />
              <TextField size="small" label="business_outcome" value={manualOutcome} onChange={(e) => setManualOutcome(e.target.value)} />
            </>
          )}
          {verificationMode === "http_api" && (
            <>
              <TextField
                size="small"
                label="url"
                value={httpUrl}
                onChange={(e) => setHttpUrl(e.target.value)}
                sx={{ minWidth: 260 }}
              />
              <TextField
                select
                size="small"
                label="method"
                value={httpMethod}
                onChange={(e) => setHttpMethod(e.target.value)}
                sx={{ minWidth: 120 }}
              >
                <MenuItem value="GET">GET</MenuItem>
                <MenuItem value="POST">POST</MenuItem>
              </TextField>
              <TextField
                size="small"
                type="number"
                label="expected_status"
                value={httpExpectedStatus}
                onChange={(e) => setHttpExpectedStatus(Number(e.target.value))}
              />
              <TextField
                size="small"
                type="number"
                label="timeout_s"
                value={httpTimeoutSeconds}
                onChange={(e) => setHttpTimeoutSeconds(Number(e.target.value))}
              />
              <TextField
                size="small"
                type="number"
                label="retries"
                value={httpRetries}
                onChange={(e) => setHttpRetries(Number(e.target.value))}
              />
              <TextField
                size="small"
                label="response_json_path"
                value={httpResponseJsonPath}
                onChange={(e) => setHttpResponseJsonPath(e.target.value)}
                sx={{ minWidth: 220 }}
              />
              <Typography variant="caption" color="text.secondary" data-testid="response-json-path-hint">
                Формат: `$.field.subfield` (пример: `$.result.status`)
              </Typography>
              <Stack direction="row" spacing={1}>
                <Button size="small" variant="outlined" onClick={() => applyPathTemplate("$.result.status")}>
                  $.result.status
                </Button>
                <Button size="small" variant="outlined" onClick={() => applyPathTemplate("$.data.state")}>
                  $.data.state
                </Button>
                <Button size="small" variant="outlined" onClick={() => applyPathTemplate("$.meta.success")}>
                  $.meta.success
                </Button>
              </Stack>
              <TextField
                size="small"
                label="expected_json_value (json)"
                value={httpExpectedJsonValueRaw}
                onChange={(e) => setHttpExpectedJsonValueRaw(e.target.value)}
                sx={{ minWidth: 220 }}
              />
              <TextField
                size="small"
                label="headers (json)"
                value={httpHeadersJson}
                onChange={(e) => setHttpHeadersJson(e.target.value)}
                multiline
                minRows={2}
                sx={{ minWidth: 260 }}
              />
              <TextField
                size="small"
                label="body (json)"
                value={httpBodyJson}
                onChange={(e) => setHttpBodyJson(e.target.value)}
                multiline
                minRows={2}
                sx={{ minWidth: 260 }}
              />
              <TextField
                size="small"
                label="preview response (json)"
                value={httpPreviewResponseJson}
                onChange={(e) => setHttpPreviewResponseJson(e.target.value)}
                multiline
                minRows={2}
                sx={{ minWidth: 320 }}
              />
              <Stack direction="row" spacing={1}>
                <Button size="small" variant="outlined" onClick={formatHttpJson}>
                  Format JSON
                </Button>
                <Button size="small" variant="outlined" onClick={validateHttpJson}>
                  Validate JSON
                </Button>
                <Button size="small" variant="outlined" onClick={runHttpPreview}>
                  Live Preview
                </Button>
                <Button size="small" variant="outlined" onClick={useLastEvidencePayloadAsPreview}>
                  Use last evidence payload as preview
                </Button>
              </Stack>
              {httpJsonHelperMessage && (
                <Typography variant="caption" color={httpJsonHelperError ? "error.main" : "success.main"}>
                  {httpJsonHelperMessage}
                </Typography>
              )}
              {httpPreviewMessage && (
                <Typography variant="caption" color={httpPreviewError ? "error.main" : "success.main"}>
                  {httpPreviewMessage}
                </Typography>
              )}
            </>
          )}
          {verificationMode === "sql_query" && (
            <>
              <TextField size="small" type="number" label="row_count" value={sqlRowCount} onChange={(e) => setSqlRowCount(Number(e.target.value))} />
              <TextField
                size="small"
                type="number"
                label="min_required"
                value={sqlMinRequired}
                onChange={(e) => setSqlMinRequired(Number(e.target.value))}
              />
            </>
          )}
          {verificationMode === "file" && (
            <TextField select size="small" label="file_exists" value={fileExists} onChange={(e) => setFileExists(e.target.value)} sx={{ minWidth: 140 }}>
              <MenuItem value="true">true</MenuItem>
              <MenuItem value="false">false</MenuItem>
            </TextField>
          )}
          {verificationMode === "webhook" && (
            <TextField
              select
              size="small"
              label="webhook_received"
              value={webhookReceived}
              onChange={(e) => setWebhookReceived(e.target.value)}
              sx={{ minWidth: 170 }}
            >
              <MenuItem value="true">true</MenuItem>
              <MenuItem value="false">false</MenuItem>
            </TextField>
          )}
        </Stack>
        <Stack direction="row" spacing={1} flexWrap="wrap">
          {(query.data?.allowed_actions ?? []).map((action) => (
            <Button key={action} size="small" variant="outlined" onClick={() => actionMutation.mutate(action)}>
              {action}
            </Button>
          ))}
        </Stack>
      </Paper>
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Stack spacing={2}>
              <TextField
                label="Прогресс (%)"
                type="number"
                value={progress}
                onChange={(e) => setProgress(Number(e.target.value))}
              />
              <TextField
                label="Комментарий прогресса"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                multiline
                minRows={4}
              />
              <Button variant="contained" onClick={() => save.mutate()} disabled={save.isPending}>
                Сохранить
              </Button>
              {isConflictError && (
                <Stack direction="row" spacing={1}>
                  <Button size="small" variant="outlined" onClick={() => qc.invalidateQueries({ queryKey: ["assignment", id] })}>
                    Reload latest
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => {
                      if (lastSavePayload) {
                        setProgress(lastSavePayload.progress_completion);
                        setNote(lastSavePayload.progress_note);
                        save.mutate();
                      }
                    }}
                    disabled={!lastSavePayload}
                  >
                    Retry save
                  </Button>
                </Stack>
              )}
            </Stack>
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Status history
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>From</TableCell>
                    <TableCell>To</TableCell>
                    <TableCell>Причина</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(query.data?.status_history ?? []).map((h) => (
                    <TableRow key={h.id}>
                      <TableCell>{h.from_status ?? "-"}</TableCell>
                      <TableCell>{h.to_status}</TableCell>
                      <TableCell>{h.reason ?? "-"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
          <Paper sx={{ p: 2, mt: 2 }}>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Verification evidence
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Статус</TableCell>
                    <TableCell>Исход</TableCell>
                    <TableCell>Тех. ошибка</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(query.data?.evidence ?? []).map((e) => (
                    <TableRow key={e.id}>
                      <TableCell>{e.verification_status}</TableCell>
                      <TableCell>{e.business_outcome ?? "-"}</TableCell>
                      <TableCell>{e.technical_error_code ?? "-"}</TableCell>
                    </TableRow>
                  ))}
                  {(query.data?.evidence ?? []).length === 0 && (
                    <TableRow>
                      <TableCell colSpan={3}>Нет evidence</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
          <Paper sx={{ p: 2, mt: 2 }}>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Revisions
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap">
              {(query.data?.revisions ?? []).slice(0, 5).map((r) => (
                <Button key={r.id} size="small" variant="outlined" onClick={() => revert.mutate(r.revision)}>
                  Revert rev {r.revision}
                </Button>
              ))}
            </Stack>
          </Paper>
          <Paper sx={{ p: 2, mt: 2 }}>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Touchpoints / аудит действий
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Когда</TableCell>
                    <TableCell>Канал</TableCell>
                    <TableCell>Тип</TableCell>
                    <TableCell>Actor</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(query.data?.touchpoints ?? []).map((t) => (
                    <TableRow key={t.id}>
                      <TableCell>{formatDate(t.created_at)}</TableCell>
                      <TableCell>{t.channel}</TableCell>
                      <TableCell>{t.kind}</TableCell>
                      <TableCell>{t.actor_id ?? "-"}</TableCell>
                    </TableRow>
                  ))}
                  {(query.data?.touchpoints ?? []).length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4}>Нет touchpoints</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>
      </Grid>
    </Stack>
  );
}
