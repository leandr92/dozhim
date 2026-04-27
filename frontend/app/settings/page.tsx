"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Paper, Stack, TextField, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import NotificationStack from "@/components/NotificationStack";
import { fetchSettings, saveSettings } from "@/lib/api";
import { useMutationNotifications, useQueryNotifications } from "@/hooks/useNotifications";

export default function SettingsPage() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["settings"], queryFn: fetchSettings });
  const [timezone, setTimezone] = useState("Europe/Moscow");
  const [queueRedZone, setQueueRedZone] = useState(30);

  useEffect(() => {
    if (query.data) {
      setTimezone(query.data.timezone ?? "Europe/Moscow");
      setQueueRedZone(query.data.queue_red_zone ?? 30);
    }
  }, [query.data]);

  const save = useMutation({
    mutationFn: () => saveSettings({ timezone, queue_red_zone: queueRedZone }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });
  const queryNotifications = useQueryNotifications([
    { id: "settings-load", error: query.error, fallback: "Не удалось загрузить настройки" },
  ]);
  const mutationNotifications = useMutationNotifications([
    {
      id: "settings-save",
      error: save.error ?? undefined,
      success: save.isSuccess,
      errorFallback: "Не удалось сохранить настройки",
      successMessage: "Настройки сохранены",
    },
  ]);
  const notifications = [...queryNotifications, ...mutationNotifications];

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Настройки</Typography>
      <NotificationStack items={notifications} />
      <Paper sx={{ p: 2 }}>
        <Stack spacing={2}>
          <TextField
            label="Timezone"
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
          />
          <TextField
            label="Красная зона очереди"
            type="number"
            value={queueRedZone}
            onChange={(e) => setQueueRedZone(Number(e.target.value))}
          />
          <Button variant="contained" onClick={() => save.mutate()} disabled={save.isPending}>
            Сохранить
          </Button>
        </Stack>
      </Paper>
    </Stack>
  );
}
