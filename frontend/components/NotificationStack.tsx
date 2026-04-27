"use client";

import { useEffect, useMemo, useState } from "react";
import { Alert, AlertTitle, Stack } from "@mui/material";

export type NotificationItem = {
  id: string;
  type: "error" | "warning" | "info" | "success";
  message: string;
  title?: string;
  sticky?: boolean;
  autoHideMs?: number;
};

type Props = {
  items: NotificationItem[];
};

export default function NotificationStack({ items }: Props) {
  const [dismissed, setDismissed] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const timers: Array<ReturnType<typeof setTimeout>> = [];
    for (const item of items) {
      const isSticky = item.sticky ?? item.type === "error";
      if (isSticky || dismissed[item.id]) continue;
      const timeout = item.autoHideMs ?? 30000;
      timers.push(
        setTimeout(() => {
          setDismissed((prev) => ({ ...prev, [item.id]: true }));
        }, timeout)
      );
    }
    return () => timers.forEach((t) => clearTimeout(t));
  }, [items, dismissed]);

  const visible = useMemo(() => items.filter((x) => !dismissed[x.id]), [items, dismissed]);
  if (visible.length === 0) return null;

  return (
    <Stack spacing={1}>
      {visible.map((item) => (
        <Alert
          key={item.id}
          severity={item.type}
          onClose={() => setDismissed((prev) => ({ ...prev, [item.id]: true }))}
        >
          {item.title && <AlertTitle>{item.title}</AlertTitle>}
          {item.message}
        </Alert>
      ))}
    </Stack>
  );
}
