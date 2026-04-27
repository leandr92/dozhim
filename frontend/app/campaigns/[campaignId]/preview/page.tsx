"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Button,
  Chip,
  Grid,
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

import {
  approveSendCampaign,
  fetchCampaignMessages,
  getErrorText,
  patchCampaignMessage,
  retryFailedCampaign,
  setManualSentFlag
} from "@/lib/api";
import { useInfoNotifications, useMutationNotifications, useQueryNotifications } from "@/hooks/useNotifications";

type Props = { params: { campaignId: string } };

export default function CampaignPreviewPage({ params }: Props) {
  const queryClient = useQueryClient();
  const campaignId = params.campaignId;
  const query = useQuery({
    queryKey: ["campaign", campaignId],
    queryFn: () => fetchCampaignMessages(campaignId),
    refetchInterval: 5000
  });

  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);
  const selected = useMemo(
    () => query.data?.items.find((x) => x.id === selectedMessageId) ?? query.data?.items[0] ?? null,
    [query.data?.items, selectedMessageId]
  );
  const [form, setForm] = useState({ subject: "", body: "", to_email: "", cc_emails: "" });
  const [fallbackComment, setFallbackComment] = useState("");

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!selected) return;
      return patchCampaignMessage(campaignId, selected.id, {
        subject: form.subject,
        body: form.body,
        to_email: form.to_email,
        cc_emails: form.cc_emails.split(",").map((x) => x.trim()).filter(Boolean)
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] });
    }
  });

  const approveMutation = useMutation({
    mutationFn: () => approveSendCampaign(campaignId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] })
  });

  const retryMutation = useMutation({
    mutationFn: () => retryFailedCampaign(campaignId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] })
  });

  const manualSentMutation = useMutation({
    mutationFn: () => {
      if (!selected) return Promise.resolve();
      return setManualSentFlag(campaignId, selected.id, fallbackComment);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] })
  });
  const queryNotifications = useQueryNotifications([
    { id: "campaign-load", error: query.error, fallback: "Не удалось загрузить кампанию" },
  ]);
  const mutationNotifications = useMutationNotifications([
    {
      id: "campaign-action",
      error: saveMutation.error ?? approveMutation.error ?? retryMutation.error ?? manualSentMutation.error ?? undefined,
      success: saveMutation.isSuccess || approveMutation.isSuccess || retryMutation.isSuccess || manualSentMutation.isSuccess,
      errorFallback: "Не удалось выполнить действие с кампанией",
      successMessage: "Действие по кампании выполнено",
    },
  ]);
  const infoNotifications = useInfoNotifications([
    {
      id: "campaign-payload-immutable",
      enabled: !!selected?.is_payload_immutable,
      message: "Payload immutable: сообщение уже отправлено.",
    },
    {
      id: "campaign-fallback-comment",
      enabled: !!selected?.manual_fallback_comment,
      message: `Fallback comment: ${selected?.manual_fallback_comment ?? ""}`,
    },
  ]);
  const notifications = [...queryNotifications, ...mutationNotifications, ...infoNotifications];

  if (query.isLoading) return <Typography>Загрузка...</Typography>;
  if (query.isError || !query.data) return <NotificationStack items={notifications} />;

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Campaign Preview & Edit</Typography>
      <Stack direction="row" spacing={1}>
        <Chip label={`ready: ${query.data.counters.ready}`} />
        <Chip label={`sent: ${query.data.counters.sent}`} />
        <Chip label={`blocked: ${query.data.counters.blocked}`} />
        <Chip label={`review_required: ${query.data.counters.review_required}`} />
      </Stack>
      <NotificationStack items={notifications} />
      <Stack direction="row" spacing={1}>
        <Button variant="contained" onClick={() => approveMutation.mutate()} disabled={approveMutation.isPending}>
          Approve and Send
        </Button>
        <Button variant="outlined" onClick={() => retryMutation.mutate()} disabled={retryMutation.isPending}>
          Retry failed
        </Button>
      </Stack>
      <Grid container spacing={2}>
        <Grid item xs={12} md={5}>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>To</TableCell>
                  <TableCell>Статус</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {query.data.items.map((msg) => (
                  <TableRow
                    key={msg.id}
                    hover
                    selected={selected?.id === msg.id}
                    onClick={() => {
                      setSelectedMessageId(msg.id);
                      setForm({
                        subject: msg.subject,
                        body: msg.body,
                        to_email: msg.to_email,
                        cc_emails: msg.cc_emails.join(", ")
                      });
                    }}
                    sx={{
                      cursor: "pointer",
                      opacity: msg.is_payload_immutable ? 0.75 : 1,
                      backgroundColor: msg.is_payload_immutable ? "action.disabledBackground" : "inherit"
                    }}
                  >
                    <TableCell>{msg.to_email || "-"}</TableCell>
                    <TableCell>{msg.status}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Grid>
        <Grid item xs={12} md={7}>
          <Paper sx={{ p: 2 }}>
            {!selected ? (
              <Typography>Выберите сообщение</Typography>
            ) : (
              <Box sx={{ display: "grid", gap: 2 }}>
                <TextField
                  label="To"
                  value={form.to_email}
                  onChange={(e) => setForm((s) => ({ ...s, to_email: e.target.value }))}
                  disabled={selected.is_payload_immutable}
                />
                <TextField
                  label="CC"
                  value={form.cc_emails}
                  onChange={(e) => setForm((s) => ({ ...s, cc_emails: e.target.value }))}
                  disabled={selected.is_payload_immutable}
                />
                <TextField
                  label="Subject"
                  value={form.subject}
                  onChange={(e) => setForm((s) => ({ ...s, subject: e.target.value }))}
                  disabled={selected.is_payload_immutable}
                />
                <TextField
                  label="Body"
                  multiline
                  minRows={8}
                  value={form.body}
                  onChange={(e) => setForm((s) => ({ ...s, body: e.target.value }))}
                  disabled={selected.is_payload_immutable}
                />
                <Button
                  variant="contained"
                  onClick={() => saveMutation.mutate()}
                  disabled={selected.is_payload_immutable || saveMutation.isPending}
                >
                  Save
                </Button>
                <TextField
                  label="Комментарий fallback (ручная отправка)"
                  value={fallbackComment}
                  onChange={(e) => setFallbackComment(e.target.value)}
                  disabled={selected.is_payload_immutable}
                />
                <Button
                  variant="outlined"
                  onClick={() => manualSentMutation.mutate()}
                  disabled={selected.is_payload_immutable || !fallbackComment.trim() || manualSentMutation.isPending}
                >
                  Manual sent flag
                </Button>
              </Box>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Stack>
  );
}
