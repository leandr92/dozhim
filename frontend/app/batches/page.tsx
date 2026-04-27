"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Paper, Stack, TextField, Typography } from "@mui/material";
import { useState } from "react";

import NotificationStack from "@/components/NotificationStack";
import { createBatch, fetchBatch, fetchPeople, fetchTemplates, retryBatch } from "@/lib/api";
import { useMutationNotifications } from "@/hooks/useNotifications";

export default function BatchesPage() {
  const queryClient = useQueryClient();
  const people = useQuery({ queryKey: ["people"], queryFn: fetchPeople });
  const templates = useQuery({ queryKey: ["templates"], queryFn: fetchTemplates });
  const [projectId, setProjectId] = useState("system-project");
  const [templateId, setTemplateId] = useState("");
  const [name, setName] = useState("");
  const [peopleIdsCsv, setPeopleIdsCsv] = useState("");
  const [selectedBatchId, setSelectedBatchId] = useState("");
  const batchQuery = useQuery({
    queryKey: ["batch", selectedBatchId],
    queryFn: () => fetchBatch(selectedBatchId),
    enabled: Boolean(selectedBatchId)
  });

  const create = useMutation({
    mutationFn: () =>
      createBatch({
        project_id: projectId,
        template_id: templateId || undefined,
        name,
        people_ids: peopleIdsCsv
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean)
      }),
    onSuccess: (result) => {
      setSelectedBatchId(result.id);
      queryClient.invalidateQueries({ queryKey: ["batch", result.id] });
    }
  });
  const retry = useMutation({
    mutationFn: (batchId: string) => retryBatch(batchId),
    onSuccess: (result) => {
      setSelectedBatchId(result.id);
      queryClient.invalidateQueries({ queryKey: ["batch", result.id] });
    }
  });

  const notifications = useMutationNotifications([
    {
      id: "batches-mutate",
      error: create.error ?? retry.error ?? undefined,
      success: create.isSuccess || retry.isSuccess,
      errorFallback: "Не удалось выполнить batch операцию",
      successMessage: "Batch операция выполнена"
    }
  ]);

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Batch Runs</Typography>
      <NotificationStack items={notifications} />
      <Paper sx={{ p: 2 }}>
        <Stack spacing={2}>
          <TextField size="small" label="project_id" value={projectId} onChange={(e) => setProjectId(e.target.value)} />
          <TextField
            size="small"
            label="template_id (опц.)"
            value={templateId}
            onChange={(e) => setTemplateId(e.target.value)}
            helperText={`Доступно шаблонов: ${templates.data?.items.length ?? 0}`}
          />
          <TextField size="small" label="Название batch" value={name} onChange={(e) => setName(e.target.value)} />
          <TextField
            size="small"
            label="people_ids через запятую (опц.)"
            value={peopleIdsCsv}
            onChange={(e) => setPeopleIdsCsv(e.target.value)}
            helperText={`Активных людей: ${(people.data?.items ?? []).filter((x) => x.is_active).length}`}
          />
          <Button variant="contained" onClick={() => create.mutate()} disabled={create.isPending || !name.trim()}>
            Запустить batch
          </Button>
        </Stack>
      </Paper>
      <Paper sx={{ p: 2 }}>
        <Stack spacing={1}>
          <TextField
            size="small"
            label="Batch ID для просмотра/ретрая"
            value={selectedBatchId}
            onChange={(e) => setSelectedBatchId(e.target.value)}
          />
          <Stack direction="row" spacing={1}>
            <Button size="small" onClick={() => batchQuery.refetch()} disabled={!selectedBatchId}>
              Обновить статус
            </Button>
            <Button size="small" color="warning" onClick={() => retry.mutate(selectedBatchId)} disabled={!selectedBatchId || retry.isPending}>
              Retry batch
            </Button>
          </Stack>
          {batchQuery.data && (
            <Typography variant="body2">
              status: {batchQuery.data.status}, result: {JSON.stringify(batchQuery.data.result ?? {})}
            </Typography>
          )}
        </Stack>
      </Paper>
    </Stack>
  );
}
