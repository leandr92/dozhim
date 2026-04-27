"use client";

import { useMemo } from "react";

import { NotificationItem } from "@/components/NotificationStack";
import { getErrorText } from "@/lib/api";

type QueryNotificationConfig = {
  id: string;
  error: unknown;
  fallback: string;
  title?: string;
};

type MutationNotificationConfig = {
  id: string;
  error?: unknown;
  success?: boolean;
  errorFallback: string;
  successMessage: string;
  title?: string;
};

type InfoNotificationConfig = {
  id: string;
  enabled: boolean;
  message: string;
  title?: string;
};

export function useQueryNotifications(configs: QueryNotificationConfig[]): NotificationItem[] {
  return useMemo(
    () =>
      configs
        .filter((c) => !!c.error)
        .map((c) => ({
          id: c.id,
          type: "error" as const,
          title: c.title ?? "Ошибка",
          message: getErrorText(c.error, c.fallback),
        })),
    [configs]
  );
}

export function useMutationNotifications(configs: MutationNotificationConfig[]): NotificationItem[] {
  return useMemo(() => {
    const items: NotificationItem[] = [];
    for (const c of configs) {
      if (c.error) {
        items.push({
          id: `${c.id}-error`,
          type: "error",
          title: c.title ?? "Ошибка",
          message: getErrorText(c.error, c.errorFallback),
        });
      } else if (c.success) {
        items.push({
          id: `${c.id}-success`,
          type: "success",
          title: "Успешно",
          message: c.successMessage,
        });
      }
    }
    return items;
  }, [configs]);
}

export function useInfoNotifications(configs: InfoNotificationConfig[]): NotificationItem[] {
  return useMemo(
    () =>
      configs
        .filter((c) => c.enabled)
        .map((c) => ({
          id: c.id,
          type: "info" as const,
          title: c.title ?? "Информация",
          message: c.message,
        })),
    [configs]
  );
}
