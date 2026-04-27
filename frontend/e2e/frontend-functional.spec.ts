import { expect, test } from "@playwright/test";

test("dashboard shows counters from API and supports navigation", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/health")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok" }) });
      return;
    }
    if (url.pathname.endsWith("/assignments")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], page: 1, page_size: 50, total: 12 })
      });
      return;
    }
    if (url.pathname.endsWith("/jobs")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], page: 1, page_size: 50, total: 7 })
      });
      return;
    }
    if (url.pathname.endsWith("/metrics/kpi")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ totals: { assignments: 12, done: 6, cannot_be_done: 0, overdue: 6 }, kpi: { outcome_ratio: 0.5, outcome_percent: 50 } })
      });
      return;
    }
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not mocked" }) });
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByText("ok")).toBeVisible();
  await expect(page.getByText("12")).toBeVisible();
  await expect(page.getByText("7")).toBeVisible();
  await expect(page.getByText("50%")).toBeVisible();

  await page.getByRole("button", { name: "Задачи" }).click();
  await expect(page).toHaveURL(/\/assignments$/);
});

test("assignments page allows manual create flow", async ({ page }) => {
  const state = {
    items: [] as Array<{
      id: string;
      title: string;
      status: string;
      project_id: string;
      target_object_id: string;
      revision: number;
      deadline_at: null;
    }>
  };

  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/assignments") && route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: state.items, page: 1, page_size: 50, total: state.items.length })
      });
      return;
    }
    if (url.pathname.endsWith("/assignments") && route.request().method() === "POST") {
      const body = route.request().postDataJSON() as {
        project_id: string;
        title: string;
        target_object_external_key: string;
      };
      state.items.unshift({
        id: "a-1",
        title: body.title,
        status: "new",
        project_id: body.project_id,
        target_object_id: body.target_object_external_key,
        revision: 1,
        deadline_at: null
      });
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "a-1", task_code: "T-00000001", created: true }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
  });

  await page.goto("/assignments");
  await page.getByLabel("Название").fill("Актуализировать проект");
  await page.getByLabel("target_object_external_key").fill("OBJ-001");
  await page.getByRole("button", { name: "Создать" }).click();

  await expect(page.getByText("Актуализировать проект")).toBeVisible();
  await expect(page.getByRole("button", { name: "Открыть" })).toBeVisible();
});

test("assignment details supports JSON-path hint and evidence preview fallback", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/assignments/a-1")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          assignment: {
            id: "a-1",
            task_code: "T-00000001",
            title: "Проверка верификации",
            status: "in_progress",
            project_id: "system-project",
            target_object_id: "obj-1",
            deadline_at: null,
            progress_completion: 0,
            progress_note: null,
            next_commitment_date: null,
            revision: 1,
            created_at: "2026-04-27T12:00:00Z",
            updated_at: "2026-04-27T12:00:00Z"
          },
          allowed_actions: ["run_verification"],
          status_history: [],
          evidence: [
            {
              id: "ev-1",
              verification_status: "verified",
              business_outcome: "done",
              technical_error_code: null,
              payload: {
                response_body: {
                  result: { status: "ok" }
                },
                raw: true
              },
              created_at: "2026-04-27T12:10:00Z"
            }
          ],
          revisions: []
        })
      });
      return;
    }
    if (url.pathname.endsWith("/assignments/a-1/actions")) {
      await route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ job_id: "job-1" }) });
      return;
    }
    if (url.pathname.endsWith("/assignments/a-1/actions/allowed")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ assignment_id: "a-1", status: "in_progress", allowed_actions: ["run_verification"] })
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
  });

  await page.goto("/assignments/a-1");
  await expect(page.getByText("Формат: `$.field.subfield` (пример: `$.result.status`)")).toBeVisible();

  await page.getByRole("button", { name: "Use last evidence payload as preview" }).click();
  const previewField = page.getByLabel("preview response (json)");
  await expect(previewField).toContainText('"result"');
  await expect(previewField).toContainText('"status": "ok"');
  await expect(page.getByText("Preview JSON обновлен из payload.response_body")).toBeVisible();
});
