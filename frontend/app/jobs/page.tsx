"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";
import NotificationStack from "@/components/NotificationStack";
import { fetchJobs, retryJob } from "@/lib/api";
import { useMutationNotifications, useQueryNotifications } from "@/hooks/useNotifications";

export default function JobsPage() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["jobs"], queryFn: fetchJobs, refetchInterval: 5000 });
  const retry = useMutation({
    mutationFn: (jobId: string) => retryJob(jobId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] })
  });
  const queryNotifications = useQueryNotifications([
    { id: "jobs-load", error: query.error, fallback: "Не удалось загрузить jobs" },
  ]);
  const mutationNotifications = useMutationNotifications([
    {
      id: "jobs-retry",
      error: retry.error ?? undefined,
      success: retry.isSuccess,
      errorFallback: "Не удалось выполнить retry",
      successMessage: "Retry job поставлен в очередь",
    },
  ]);
  const notifications = [...queryNotifications, ...mutationNotifications];

  return (
    <>
      <Typography variant="h4" sx={{ mb: 2 }}>
        Jobs
      </Typography>
      <NotificationStack items={notifications} />
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Тип</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell>Retry</TableCell>
              <TableCell>Error</TableCell>
              <TableCell>Correlation</TableCell>
              <TableCell>Создано</TableCell>
              <TableCell>Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(query.data?.items ?? []).map((job) => (
              <TableRow key={job.id}>
                <TableCell>{job.id}</TableCell>
                <TableCell>{job.kind}</TableCell>
                <TableCell>
                  <Chip label={job.status} size="small" />
                </TableCell>
                <TableCell>{job.retry_count}</TableCell>
                <TableCell>{job.error?.message ?? "-"}</TableCell>
                <TableCell>{job.error?.correlation_id ?? "-"}</TableCell>
                <TableCell>{job.created_at}</TableCell>
                <TableCell>
                  <Button
                    size="small"
                    disabled={!["failed", "timed_out", "cancelled"].includes(job.status) || retry.isPending}
                    onClick={() => retry.mutate(job.id)}
                  >
                    Retry
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {!query.isLoading && (query.data?.items.length ?? 0) === 0 && (
              <TableRow>
                <TableCell colSpan={8}>Нет jobs</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
}
