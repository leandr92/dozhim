"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Paper,
  MenuItem,
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
import Link from "next/link";
import { useState } from "react";

import NotificationStack from "@/components/NotificationStack";
import { createAssignment, deleteAssignment, fetchAssignments } from "@/lib/api";
import { useMutationNotifications, useQueryNotifications } from "@/hooks/useNotifications";

export default function AssignmentsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [projectFilter, setProjectFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sortBy, setSortBy] = useState<"created_at" | "deadline_at">("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const query = useQuery({
    queryKey: ["assignments", page, projectFilter, statusFilter, sortBy, sortDir],
    queryFn: () =>
      fetchAssignments({
        page,
        page_size: 20,
        project_id: projectFilter || undefined,
        status_filter: statusFilter || undefined,
        sort_by: sortBy,
        sort_dir: sortDir
      })
  });
  const [projectId, setProjectId] = useState("system-project");
  const [title, setTitle] = useState("");
  const [targetObjectExternalKey, setTargetObjectExternalKey] = useState("");
  const [targetObjectName, setTargetObjectName] = useState("");
  const create = useMutation({
    mutationFn: () =>
      createAssignment({
        project_id: projectId.trim(),
        title: title.trim(),
        target_object_external_key: targetObjectExternalKey.trim(),
        target_object_name: targetObjectName.trim() || undefined
      }),
    onSuccess: () => {
      setTitle("");
      setTargetObjectExternalKey("");
      setTargetObjectName("");
      queryClient.invalidateQueries({ queryKey: ["assignments"] });
    }
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteAssignment(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assignments"] })
  });
  const queryNotifications = useQueryNotifications([
    { id: "assignments-load", error: query.error, fallback: "Не удалось загрузить задачи" },
  ]);
  const mutationNotifications = useMutationNotifications([
    {
      id: "assignments-manual-create",
      error: create.error ?? remove.error ?? undefined,
      success: create.isSuccess || remove.isSuccess,
      errorFallback: "Не удалось выполнить операцию с задачей",
      successMessage: "Операция по задаче выполнена",
    }
  ]);
  const notifications = [...queryNotifications, ...mutationNotifications];

  return (
    <>
      <Typography variant="h4" sx={{ mb: 2 }}>
        Задачи
      </Typography>
      <NotificationStack items={notifications} />
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Фильтры
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
          <TextField
            size="small"
            label="project_id"
            value={projectFilter}
            onChange={(e) => {
              setPage(1);
              setProjectFilter(e.target.value);
            }}
          />
          <TextField
            size="small"
            label="Статус"
            value={statusFilter}
            onChange={(e) => {
              setPage(1);
              setStatusFilter(e.target.value);
            }}
          />
          <TextField size="small" select label="Сортировка" value={sortBy} onChange={(e) => setSortBy(e.target.value as "created_at" | "deadline_at")}>
            <MenuItem value="created_at">created_at</MenuItem>
            <MenuItem value="deadline_at">deadline_at</MenuItem>
          </TextField>
          <TextField size="small" select label="Направление" value={sortDir} onChange={(e) => setSortDir(e.target.value as "asc" | "desc")}>
            <MenuItem value="desc">desc</MenuItem>
            <MenuItem value="asc">asc</MenuItem>
          </TextField>
        </Stack>
      </Paper>
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Ручное создание задачи
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          <TextField
            size="small"
            label="project_id"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
          />
          <TextField size="small" label="Название" value={title} onChange={(e) => setTitle(e.target.value)} />
          <TextField
            size="small"
            label="target_object_external_key"
            value={targetObjectExternalKey}
            onChange={(e) => setTargetObjectExternalKey(e.target.value)}
          />
          <TextField
            size="small"
            label="Название объекта (опц.)"
            value={targetObjectName}
            onChange={(e) => setTargetObjectName(e.target.value)}
          />
          <Button
            variant="contained"
            onClick={() => create.mutate()}
            disabled={create.isPending || !projectId.trim() || !title.trim() || !targetObjectExternalKey.trim()}
          >
            Создать
          </Button>
        </Stack>
      </Paper>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Название</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell>Проект</TableCell>
              <TableCell>Объект</TableCell>
              <TableCell>Revision</TableCell>
              <TableCell>Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(query.data?.items ?? []).map((a) => (
              <TableRow key={a.id}>
                <TableCell>{a.title}</TableCell>
                <TableCell>{a.status}</TableCell>
                <TableCell>{a.project_id}</TableCell>
                <TableCell>{a.target_object_id}</TableCell>
                <TableCell>{a.revision}</TableCell>
                <TableCell>
                  <Button component={Link} href={`/assignments/${a.id}`} size="small">
                    Открыть
                  </Button>
                  <Button
                    size="small"
                    color="error"
                    onClick={() => remove.mutate(a.id)}
                    disabled={remove.isPending}
                  >
                    Удалить
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {!query.isLoading && (query.data?.items.length ?? 0) === 0 && (
              <TableRow>
                <TableCell colSpan={6}>Нет данных</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
      <Stack direction="row" spacing={1}>
        <Button size="small" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
          Назад
        </Button>
        <Typography variant="body2" sx={{ display: "flex", alignItems: "center" }}>
          Страница {page}
        </Typography>
        <Button
          size="small"
          disabled={(query.data?.items.length ?? 0) < 20}
          onClick={() => setPage((p) => p + 1)}
        >
          Вперед
        </Button>
      </Stack>
    </>
  );
}
