"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Chip,
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
  Typography,
} from "@mui/material";
import { useMemo, useState } from "react";

import NotificationStack from "@/components/NotificationStack";
import { AuditLogsFilters, fetchAuditLogs } from "@/lib/api";
import { useQueryNotifications } from "@/hooks/useNotifications";

function toIso(date: Date): string {
  return date.toISOString();
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "medium" }).format(new Date(value));
}

export default function AuditPage() {
  const [filters, setFilters] = useState<AuditLogsFilters>({ sort_by: "created_at", sort_dir: "desc" });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [actorInput, setActorInput] = useState("");
  const [pathInput, setPathInput] = useState("");
  const [statusInput, setStatusInput] = useState("");
  const [fromTs, setFromTs] = useState("");
  const [toTs, setToTs] = useState("");

  const query = useQuery({
    queryKey: ["audit-logs", filters, page, pageSize],
    queryFn: () => fetchAuditLogs({ ...filters, page, page_size: pageSize }),
    refetchInterval: 10000,
  });
  const notifications = useQueryNotifications([
    { id: "audit-load", error: query.error, fallback: "Не удалось загрузить аудит-лог" },
  ]);
  const activeFilters = useMemo(() => {
    const items: string[] = [];
    if (filters.actor_id) items.push(`actor:${filters.actor_id}`);
    if (filters.method) items.push(`method:${filters.method}`);
    if (filters.path) items.push(`path:${filters.path}`);
    if (typeof filters.status_code === "number") items.push(`status:${filters.status_code}`);
    if (filters.from_ts) items.push(`from:${filters.from_ts}`);
    if (filters.to_ts) items.push(`to:${filters.to_ts}`);
    if (filters.sort_by) items.push(`sort:${filters.sort_by}`);
    if (filters.sort_dir) items.push(`dir:${filters.sort_dir}`);
    return items;
  }, [filters]);
  const totalPages = Math.max(1, Math.ceil((query.data?.total ?? 0) / pageSize));

  const applyTimePreset = (minutes: number) => {
    const to = new Date();
    const from = new Date(to.getTime() - minutes * 60 * 1000);
    const fromIso = toIso(from);
    const toIsoValue = toIso(to);
    setFromTs(fromIso);
    setToTs(toIsoValue);
    setFilters((s) => ({
      ...s,
      from_ts: fromIso,
      to_ts: toIsoValue,
    }));
    setPage(1);
  };

  return (
    <>
      <Typography variant="h4" sx={{ mb: 2 }}>
        Аудит
      </Typography>
      <NotificationStack items={notifications} />
      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
          <Button size="small" variant="outlined" onClick={() => setFilters((s) => ({ ...s, method: "POST" }))}>
            POST
          </Button>
          <Button size="small" variant="outlined" onClick={() => setFilters((s) => ({ ...s, method: "PATCH" }))}>
            PATCH
          </Button>
          <Button size="small" variant="outlined" onClick={() => setFilters((s) => ({ ...s, status_code: 200 }))}>
            status=200
          </Button>
          <Button size="small" variant="outlined" onClick={() => setFilters((s) => ({ ...s, status_code: 403 }))}>
            status=403
          </Button>
          <Button size="small" variant="outlined" onClick={() => applyTimePreset(15)}>
            last 15m
          </Button>
          <Button size="small" variant="outlined" onClick={() => applyTimePreset(60)}>
            last 1h
          </Button>
          <Button size="small" variant="outlined" onClick={() => applyTimePreset(24 * 60)}>
            last 24h
          </Button>
          <TextField
            select
            size="small"
            label="sort_by"
            value={filters.sort_by ?? "created_at"}
            onChange={(e) => {
              const value = e.target.value as "created_at" | "status_code";
              setFilters((s) => ({ ...s, sort_by: value }));
              setPage(1);
            }}
            sx={{ width: 160 }}
          >
            <MenuItem value="created_at">created_at</MenuItem>
            <MenuItem value="status_code">status_code</MenuItem>
          </TextField>
          <TextField
            select
            size="small"
            label="sort_dir"
            value={filters.sort_dir ?? "desc"}
            onChange={(e) => {
              const value = e.target.value as "asc" | "desc";
              setFilters((s) => ({ ...s, sort_dir: value }));
              setPage(1);
            }}
            sx={{ width: 130 }}
          >
            <MenuItem value="desc">desc</MenuItem>
            <MenuItem value="asc">asc</MenuItem>
          </TextField>
          <Button size="small" color="inherit" variant="outlined" onClick={() => {
            setFilters({ sort_by: "created_at", sort_dir: "desc" });
            setPage(1);
            setActorInput("");
            setPathInput("");
            setStatusInput("");
            setFromTs("");
            setToTs("");
          }}>
            Сброс
          </Button>
        </Stack>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          <TextField size="small" label="actor_id" value={actorInput} onChange={(e) => setActorInput(e.target.value)} />
          <TextField size="small" label="path like" value={pathInput} onChange={(e) => setPathInput(e.target.value)} />
          <TextField size="small" label="status_code" value={statusInput} onChange={(e) => setStatusInput(e.target.value)} />
          <TextField size="small" label="from (ISO)" value={fromTs} onChange={(e) => setFromTs(e.target.value)} />
          <TextField size="small" label="to (ISO)" value={toTs} onChange={(e) => setToTs(e.target.value)} />
          <Button
            size="small"
            variant="contained"
            onClick={() => {
              setFilters((s) => ({
                ...s,
                actor_id: actorInput.trim() || undefined,
                path: pathInput.trim() || undefined,
                status_code: statusInput.trim() ? Number(statusInput) : undefined,
                from_ts: fromTs.trim() || undefined,
                to_ts: toTs.trim() || undefined,
                sort_by: s.sort_by ?? "created_at",
                sort_dir: s.sort_dir ?? "desc",
              }));
              setPage(1);
            }}
          >
            Применить
          </Button>
        </Stack>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 2 }}>
          {activeFilters.map((f) => (
            <Chip key={f} size="small" label={f} />
          ))}
        </Stack>
      </Paper>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Когда</TableCell>
              <TableCell>Кто</TableCell>
              <TableCell>Роль</TableCell>
              <TableCell>Action</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Correlation</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(query.data?.items ?? []).map((x) => (
              <TableRow key={x.id}>
                <TableCell>{formatDate(x.created_at)}</TableCell>
                <TableCell>{x.actor_id ?? "-"}</TableCell>
                <TableCell>{x.actor_role ?? "-"}</TableCell>
                <TableCell>{x.action}</TableCell>
                <TableCell>{x.status_code}</TableCell>
                <TableCell>{x.correlation_id ?? "-"}</TableCell>
              </TableRow>
            ))}
            {!query.isLoading && (query.data?.items.length ?? 0) === 0 && (
              <TableRow>
                <TableCell colSpan={6}>Аудит-пуст</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
      <Paper sx={{ p: 2, mt: 2 }}>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
          <Button size="small" variant="outlined" onClick={() => setPage(1)} disabled={page <= 1}>
            Первая
          </Button>
          <Button size="small" variant="outlined" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>
            Назад
          </Button>
          <Chip size="small" label={`Страница ${page} / ${totalPages}`} />
          <Button
            size="small"
            variant="outlined"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
          >
            Вперед
          </Button>
          <Button
            size="small"
            variant="outlined"
            onClick={() => setPage(totalPages)}
            disabled={page >= totalPages}
          >
            Последняя
          </Button>
          <TextField
            select
            size="small"
            label="page_size"
            value={String(pageSize)}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
            }}
            sx={{ width: 120 }}
          >
            <MenuItem value="25">25</MenuItem>
            <MenuItem value="50">50</MenuItem>
            <MenuItem value="100">100</MenuItem>
            <MenuItem value="200">200</MenuItem>
          </TextField>
          <Chip size="small" label={`Всего: ${query.data?.total ?? 0}`} />
        </Stack>
      </Paper>
    </>
  );
}
