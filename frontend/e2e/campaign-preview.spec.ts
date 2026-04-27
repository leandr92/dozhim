import { expect, test } from "@playwright/test";

test("campaign preview supports save, approve, retry and manual sent flag", async ({ page }) => {
  const state = {
    saveCalls: 0,
    approveCalls: 0,
    retryCalls: 0,
    manualSentCalls: 0,
    message: {
      id: "msg-1",
      to_email: "owner@example.com",
      cc_emails: ["curator@example.com"],
      subject: "Initial subject",
      body: "Initial body",
      status: "draft",
      is_payload_immutable: false,
      email_sent_flag: false,
      manual_fallback_comment: null as string | null,
      revision: 1
    }
  };

  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const { pathname } = url;
    const method = route.request().method();

    if (pathname.endsWith("/campaigns/cmp-1/messages") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          campaign: {
            id: "cmp-1",
            name: "Campaign 1",
            status: "draft",
            project_id: "system-project",
            import_id: "imp-1"
          },
          counters: { ready: 1, sent: 0, blocked: 0, review_required: 0 },
          items: [state.message]
        })
      });
      return;
    }

    if (pathname.endsWith("/campaigns/cmp-1/messages/msg-1") && method === "PATCH") {
      state.saveCalls += 1;
      const body = route.request().postDataJSON() as {
        subject: string;
        body: string;
        to_email: string;
        cc_emails: string[];
      };
      state.message = {
        ...state.message,
        ...body,
        cc_emails: body.cc_emails
      };
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ updated: true }) });
      return;
    }

    if (pathname.endsWith("/campaigns/cmp-1/approve-send") && method === "POST") {
      state.approveCalls += 1;
      await route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ job_id: "job-approve-1" }) });
      return;
    }

    if (pathname.endsWith("/campaigns/cmp-1/retry-failed") && method === "POST") {
      state.retryCalls += 1;
      await route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ job_id: "job-retry-1" }) });
      return;
    }

    if (pathname.endsWith("/campaigns/cmp-1/messages/msg-1/manual-sent-flag") && method === "POST") {
      state.manualSentCalls += 1;
      const body = route.request().postDataJSON() as { comment: string };
      state.message = {
        ...state.message,
        email_sent_flag: true,
        manual_fallback_comment: body.comment
      };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: state.message.id, email_sent_flag: true, manual_fallback_comment: body.comment })
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
  });

  await page.goto("/campaigns/cmp-1/preview");
  await expect(page.getByRole("heading", { name: "Campaign Preview & Edit" })).toBeVisible();

  await page.getByText("owner@example.com").click();
  await page.getByLabel("Subject").fill("Updated subject");
  await page.getByLabel("Body").fill("Updated body");
  await page.getByRole("button", { name: "Save" }).click();

  await expect.poll(() => state.saveCalls).toBe(1);
  await expect(page.getByText("Действие по кампании выполнено")).toBeVisible();

  await page.getByRole("button", { name: "Approve and Send" }).click();
  await expect.poll(() => state.approveCalls).toBe(1);

  await page.getByRole("button", { name: "Retry failed" }).click();
  await expect.poll(() => state.retryCalls).toBe(1);

  await page.getByLabel("Комментарий fallback (ручная отправка)").fill("Отправлено вручную через Outlook");
  await page.getByRole("button", { name: "Manual sent flag" }).click();
  await expect.poll(() => state.manualSentCalls).toBe(1);
  await expect(page.getByText("Fallback comment: Отправлено вручную через Outlook")).toBeVisible();
});
