import type { Metadata } from "next";
import { AppBar, Box, Button, Stack, Toolbar, Typography } from "@mui/material";
import Link from "next/link";
import { PropsWithChildren } from "react";

import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Dozhim",
  description: "Dozhim frontend shell"
};

const nav = [
  { href: "/", label: "Dashboard" },
  { href: "/assignments", label: "Задачи" },
  { href: "/campaigns", label: "Кампании" },
  { href: "/operator-queue", label: "Очередь" },
  { href: "/jobs", label: "Jobs" },
  { href: "/projects", label: "Проекты" },
  { href: "/settings", label: "Настройки" },
  { href: "/audit", label: "Аудит" }
];

export default function RootLayout({ children }: PropsWithChildren) {
  return (
    <html lang="ru">
      <body>
        <Providers>
          <AppBar position="static" color="default">
            <Toolbar>
              <Typography variant="h6" sx={{ mr: 3 }}>
                Dozhim
              </Typography>
              <Stack direction="row" spacing={1}>
                {nav.map((item) => (
                  <Button key={item.href} component={Link} href={item.href}>
                    {item.label}
                  </Button>
                ))}
              </Stack>
            </Toolbar>
          </AppBar>
          <Box sx={{ p: 3 }}>{children}</Box>
        </Providers>
      </body>
    </html>
  );
}
