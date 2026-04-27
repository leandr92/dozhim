"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, Grid, Typography } from "@mui/material";

import NotificationStack from "@/components/NotificationStack";
import { fetchAssignments, fetchHealth, fetchJobs, fetchKpi } from "@/lib/api";
import { useQueryNotifications } from "@/hooks/useNotifications";

export default function DashboardPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 30000 });
  const assignments = useQuery({ queryKey: ["assignments"], queryFn: fetchAssignments });
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: fetchJobs });
  const kpi = useQuery({ queryKey: ["kpi"], queryFn: fetchKpi });
  const notifications = useQueryNotifications([
    { id: "dashboard-health", error: health.error, fallback: "Ошибка проверки backend" },
  ]);

  return (
    <>
      <Typography variant="h4" sx={{ mb: 2 }}>
        Dashboard
      </Typography>
      <NotificationStack items={notifications} />
      <Grid container spacing={2}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2">Сервис</Typography>
              <Typography variant="h5">
                {health.data?.status ?? (health.isLoading ? "..." : "error")}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2">Задачи</Typography>
              <Typography variant="h5">{assignments.data?.total ?? 0}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2">Jobs</Typography>
              <Typography variant="h5">{jobs.data?.total ?? 0}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2">KPI Исход</Typography>
              <Typography variant="h5">{kpi.data?.kpi.outcome_percent ?? 0}%</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </>
  );
}
