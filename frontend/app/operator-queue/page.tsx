"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Chip,
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
import { useState } from "react";
import NotificationStack from "@/components/NotificationStack";

import {
  bindQueueItemToAssignment,
  claimQueueItem,
  fetchOperatorQueue,
  followUpQueueItem,
  resolveQueueItem
} from "@/lib/api";
import { useMutationNotifications, useQueryNotifications } from "@/hooks/useNotifications";

export default function OperatorQueuePage() {
  const queryClient = useQueryClient();
  const [bindMap, setBindMap] = useState<Record<string, string>>({});
  const query = useQuery({ queryKey: ["operator-queue"], queryFn: fetchOperatorQueue, refetchInterval: 7000 });

  const claim = useMutation({
    mutationFn: (id: string) => claimQueueItem(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["operator-queue"] })
  });
  const resolve = useMutation({
    mutationFn: (id: string) => resolveQueueItem(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["operator-queue"] })
  });
  const followUp = useMutation({
    mutationFn: (id: string) => followUpQueueItem(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["operator-queue"] })
  });
  const bind = useMutation({
    mutationFn: ({ itemId, assignmentId }: { itemId: string; assignmentId: string }) =>
      bindQueueItemToAssignment(itemId, assignmentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["operator-queue"] })
  });
  const queryNotifications = useQueryNotifications([
    { id: "queue-load", error: query.error, fallback: "Не удалось загрузить очередь" },
  ]);
  const mutationNotifications = useMutationNotifications([
    {
      id: "queue-action",
      error: claim.error ?? resolve.error ?? followUp.error ?? bind.error ?? undefined,
      success: claim.isSuccess || resolve.isSuccess || followUp.isSuccess || bind.isSuccess,
      errorFallback: "Не удалось выполнить действие",
      successMessage: "Действие в очереди выполнено",
    },
  ]);
  const notifications = [...queryNotifications, ...mutationNotifications];

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Очередь оператора</Typography>
      <NotificationStack items={notifications} />
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Тип</TableCell>
              <TableCell>Причина</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell>Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(query.data?.items ?? []).map((item) => (
              <TableRow key={item.id}>
                <TableCell>{item.id}</TableCell>
                <TableCell>{item.type}</TableCell>
                <TableCell>{item.reason ?? "-"}</TableCell>
                <TableCell>
                  <Chip size="small" label={item.status} />
                </TableCell>
                <TableCell>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Button size="small" onClick={() => claim.mutate(item.id)}>
                      Claim
                    </Button>
                    <Button size="small" onClick={() => resolve.mutate(item.id)}>
                      Resolve
                    </Button>
                    <Button size="small" onClick={() => followUp.mutate(item.id)}>
                      Follow-up
                    </Button>
                    {item.type === "inbound_unmatched" && (
                      <>
                        <TextField
                          size="small"
                          label="assignment_id"
                          value={bindMap[item.id] ?? ""}
                          onChange={(e) =>
                            setBindMap((prev) => ({ ...prev, [item.id]: e.target.value }))
                          }
                        />
                        <Button
                          size="small"
                          onClick={() =>
                            bind.mutate({ itemId: item.id, assignmentId: bindMap[item.id] ?? "" })
                          }
                        >
                          Bind
                        </Button>
                      </>
                    )}
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
            {!query.isLoading && (query.data?.items.length ?? 0) === 0 && (
              <TableRow>
                <TableCell colSpan={5}>Очередь пуста</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
}
