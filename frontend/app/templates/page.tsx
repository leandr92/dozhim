"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { useState } from "react";

import NotificationStack from "@/components/NotificationStack";
import { createTemplate, fetchTemplates, patchTemplate } from "@/lib/api";
import { useMutationNotifications, useQueryNotifications } from "@/hooks/useNotifications";

export default function TemplatesPage() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["templates"], queryFn: fetchTemplates });
  const [name, setName] = useState("");
  const [titleTemplate, setTitleTemplate] = useState("");
  const [deadlineDays, setDeadlineDays] = useState(7);
  const [reminderCadenceHours, setReminderCadenceHours] = useState(24);
  const [maxTextTouches, setMaxTextTouches] = useState(3);
  const [timezone, setTimezone] = useState("Europe/Moscow");

  const create = useMutation({
    mutationFn: () =>
      createTemplate({
        name,
        title_template: titleTemplate,
        default_deadline_days: deadlineDays,
        verification_policy: { method: "manual" },
        escalation_policy: { reminder_cadence_hours: reminderCadenceHours, max_text_touches: maxTextTouches, notify_manager: false },
        calendar_policy: { timezone, workday_start_local: "10:00", workday_end_local: "18:00", quiet_days: ["saturday", "sunday"] }
      }),
    onSuccess: () => {
      setName("");
      setTitleTemplate("");
      setDeadlineDays(7);
      setReminderCadenceHours(24);
      setMaxTextTouches(3);
      setTimezone("Europe/Moscow");
      queryClient.invalidateQueries({ queryKey: ["templates"] });
    }
  });
  const archive = useMutation({
    mutationFn: (id: string) => patchTemplate(id, { status: "archived" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["templates"] })
  });

  const queryNotifications = useQueryNotifications([
    { id: "templates-load", error: query.error, fallback: "Не удалось загрузить шаблоны" }
  ]);
  const mutationNotifications = useMutationNotifications([
    {
      id: "templates-mutate",
      error: create.error ?? archive.error ?? undefined,
      success: create.isSuccess || archive.isSuccess,
      errorFallback: "Не удалось выполнить действие с шаблоном",
      successMessage: "Изменения шаблона сохранены"
    }
  ]);
  const notifications = [...queryNotifications, ...mutationNotifications];

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Шаблоны и политики</Typography>
      <NotificationStack items={notifications} />
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Создать шаблон
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          <TextField size="small" label="Код шаблона" value={name} onChange={(e) => setName(e.target.value)} />
          <TextField
            size="small"
            label="Заголовок задачи (template)"
            value={titleTemplate}
            onChange={(e) => setTitleTemplate(e.target.value)}
          />
          <TextField
            size="small"
            type="number"
            label="Дней до дедлайна"
            value={deadlineDays}
            onChange={(e) => setDeadlineDays(Number(e.target.value))}
          />
          <TextField
            size="small"
            type="number"
            label="Cadence (часы)"
            value={reminderCadenceHours}
            onChange={(e) => setReminderCadenceHours(Number(e.target.value))}
          />
          <TextField
            size="small"
            type="number"
            label="Max text touches"
            value={maxTextTouches}
            onChange={(e) => setMaxTextTouches(Number(e.target.value))}
          />
          <TextField size="small" label="Timezone" value={timezone} onChange={(e) => setTimezone(e.target.value)} />
          <Button variant="contained" onClick={() => create.mutate()} disabled={create.isPending || !name.trim() || !titleTemplate.trim()}>
            Создать
          </Button>
        </Stack>
      </Paper>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Имя</TableCell>
              <TableCell>Title template</TableCell>
              <TableCell>Deadline days</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell>Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(query.data?.items ?? []).map((tpl) => (
              <TableRow key={tpl.id}>
                <TableCell>{tpl.name}</TableCell>
                <TableCell>{tpl.title_template}</TableCell>
                <TableCell>{tpl.default_deadline_days}</TableCell>
                <TableCell>{tpl.status}</TableCell>
                <TableCell>
                  <Button size="small" color="warning" onClick={() => archive.mutate(tpl.id)} disabled={tpl.status === "archived"}>
                    Архивировать
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
}
