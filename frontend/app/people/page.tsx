"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { useState } from "react";

import NotificationStack from "@/components/NotificationStack";
import { createPerson, fetchPeople, patchPerson } from "@/lib/api";
import { useMutationNotifications, useQueryNotifications } from "@/hooks/useNotifications";

export default function PeoplePage() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["people"], queryFn: fetchPeople });
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState("executor");

  const create = useMutation({
    mutationFn: () => createPerson({ full_name: fullName, email, phone, role }),
    onSuccess: () => {
      setFullName("");
      setEmail("");
      setPhone("");
      queryClient.invalidateQueries({ queryKey: ["people"] });
    }
  });
  const deactivate = useMutation({
    mutationFn: (id: string) => patchPerson(id, { is_active: false }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["people"] })
  });

  const queryNotifications = useQueryNotifications([
    { id: "people-load", error: query.error, fallback: "Не удалось загрузить людей" }
  ]);
  const mutationNotifications = useMutationNotifications([
    {
      id: "people-mutate",
      error: create.error ?? deactivate.error ?? undefined,
      success: create.isSuccess || deactivate.isSuccess,
      errorFallback: "Не удалось выполнить действие",
      successMessage: "Изменения по людям сохранены"
    }
  ]);
  const notifications = [...queryNotifications, ...mutationNotifications];

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Люди</Typography>
      <NotificationStack items={notifications} />
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Добавить человека
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          <TextField size="small" label="ФИО" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          <TextField size="small" label="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <TextField size="small" label="Телефон" value={phone} onChange={(e) => setPhone(e.target.value)} />
          <TextField size="small" label="Роль" value={role} onChange={(e) => setRole(e.target.value)} />
          <Button
            variant="contained"
            onClick={() => create.mutate()}
            disabled={create.isPending || !fullName.trim() || !email.trim() || !phone.trim()}
          >
            Создать
          </Button>
        </Stack>
      </Paper>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>ФИО</TableCell>
              <TableCell>Email</TableCell>
              <TableCell>Телефон</TableCell>
              <TableCell>Роль</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell>Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(query.data?.items ?? []).map((person) => (
              <TableRow key={person.id}>
                <TableCell>{person.full_name}</TableCell>
                <TableCell>{person.email}</TableCell>
                <TableCell>{person.phone}</TableCell>
                <TableCell>{person.role}</TableCell>
                <TableCell>{person.is_active ? "active" : "inactive"}</TableCell>
                <TableCell>
                  <Button size="small" color="warning" onClick={() => deactivate.mutate(person.id)} disabled={!person.is_active}>
                    Деактивировать
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
