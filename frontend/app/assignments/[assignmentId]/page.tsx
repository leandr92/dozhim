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

import { fetchAssignmentDetails, patchAssignment, runAssignmentAction } from "@/lib/api";
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
  const [httpHeadersJson, setHttpHeadersJson] = useState("{}");
  const [httpBodyJson, setHttpBodyJson] = useState("{}");
  const [httpJsonHelperMessage, setHttpJsonHelperMessage] = useState<string>("");
  const [httpJsonHelperError, setHttpJsonHelperError] = useState(false);
  const [sqlRowCount, setSqlRowCount] = useState(1);
  const [sqlMinRequired, setSqlMinRequired] = useState(1);
  const [fileExists, setFileExists] = useState("true");
  const [webhookReceived, setWebhookReceived] = useState("true");
  const revision = useMemo(() => assignment?.revision ?? 1, [assignment?.revision]);

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
    return { parsedHeaders, parsedBody };
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
      setHttpJsonHelperError(false);
      setHttpJsonHelperMessage("JSON отформатирован");
    } catch {
      setHttpJsonHelperError(true);
      setHttpJsonHelperMessage("Невозможно форматировать: некорректный JSON");
    }
  };

  const save = useMutation({
    mutationFn: () =>
      patchAssignment(id, {
        revision,
        progress_completion: progress,
        progress_note: note
      }),
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
                    const { parsedHeaders, parsedBody } = parseHttpJsonInputs();
                    setHttpJsonHelperError(false);
                    setHttpJsonHelperMessage("");
                    return {
                      mode: "http_api",
                      url: httpUrl,
                      method: httpMethod,
                      expected_status: httpExpectedStatus,
                      timeout_seconds: httpTimeoutSeconds,
                      retries: httpRetries,
                      headers: parsedHeaders,
                      body: parsedBody,
                    };
                  } catch {
                    setHttpJsonHelperError(true);
                    setHttpJsonHelperMessage("Некорректный JSON в HTTP headers или body");
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
      error: save.error ?? actionMutation.error ?? undefined,
      success: save.isSuccess || actionMutation.isSuccess,
      errorFallback: "Не удалось выполнить действие",
      successMessage: "Изменения по задаче сохранены",
    },
  ]);
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
              <Stack direction="row" spacing={1}>
                <Button size="small" variant="outlined" onClick={formatHttpJson}>
                  Format JSON
                </Button>
                <Button size="small" variant="outlined" onClick={validateHttpJson}>
                  Validate JSON
                </Button>
              </Stack>
              {httpJsonHelperMessage && (
                <Typography variant="caption" color={httpJsonHelperError ? "error.main" : "success.main"}>
                  {httpJsonHelperMessage}
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
        </Grid>
      </Grid>
    </Stack>
  );
}
