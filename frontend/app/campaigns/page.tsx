"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
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
import { fetchCampaigns } from "@/lib/api";
import { useQueryNotifications } from "@/hooks/useNotifications";

export default function CampaignsPage() {
  const query = useQuery({ queryKey: ["campaigns"], queryFn: fetchCampaigns, refetchInterval: 10000 });
  const notifications = useQueryNotifications([
    { id: "campaigns-load", error: query.error, fallback: "Не удалось загрузить кампании" },
  ]);

  return (
    <>
      <Typography variant="h4" sx={{ mb: 2 }}>
        Кампании
      </Typography>
      <NotificationStack items={notifications} />
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Название</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell>Проект</TableCell>
              <TableCell>Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(query.data?.items ?? []).map((campaign) => (
              <TableRow key={campaign.id}>
                <TableCell>{campaign.name}</TableCell>
                <TableCell>{campaign.status}</TableCell>
                <TableCell>{campaign.project_id}</TableCell>
                <TableCell>
                  <Button component={Link} href={`/campaigns/${campaign.id}/preview`} size="small">
                    Preview & Edit
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {!query.isLoading && (query.data?.items.length ?? 0) === 0 && (
              <TableRow>
                <TableCell colSpan={4}>Нет кампаний</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
}
