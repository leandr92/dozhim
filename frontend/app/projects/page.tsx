"use client";

import { useQuery } from "@tanstack/react-query";
import { Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from "@mui/material";
import NotificationStack from "@/components/NotificationStack";
import { fetchProjects } from "@/lib/api";
import { useQueryNotifications } from "@/hooks/useNotifications";

export default function ProjectsPage() {
  const query = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });
  const notifications = useQueryNotifications([
    { id: "projects-load", error: query.error, fallback: "Не удалось загрузить проекты" },
  ]);
  return (
    <>
      <Typography variant="h4" sx={{ mb: 2 }}>
        Проекты
      </Typography>
      <NotificationStack items={notifications} />
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Код</TableCell>
              <TableCell>Название</TableCell>
              <TableCell>Статус</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(query.data?.items ?? []).map((p: any) => (
              <TableRow key={p.id}>
                <TableCell>{p.project_code}</TableCell>
                <TableCell>{p.project_name}</TableCell>
                <TableCell>{p.status}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
}
