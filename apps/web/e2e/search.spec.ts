import { expect, test, type Page } from "@playwright/test";

const resultContent = {
  id: 62,
  source_id: 28,
  canonical_url: "https://blog.edu.dawnsynch.co.ke/why-school-work-is-not-enough-for-a-techie/",
  title: "Why School Work Is Not Enough for a Techie",
  description: "Build practical technology skills beyond coursework.",
  content_type: "article",
  author_name: "Alex",
  language_code: "en",
  thumbnail_url: null,
  duration_seconds: null,
  published_at: "2026-08-10T12:30:28Z"
};

async function mockSearch(page: Page) {
  await page.route("**/api/search?**", async (route) => {
    const requestUrl = new URL(route.request().url());
    const query = requestUrl.searchParams.get("q") ?? "";
    const mode = requestUrl.searchParams.get("mode") ?? "hybrid";

    if (query === "service failure") {
      await route.fulfill({ status: 503, json: { detail: "Unavailable" } });
      return;
    }

    const matchedBy =
      mode === "hybrid" ? ["keyword", "semantic"] : [mode];
    await route.fulfill({
      status: 200,
      json: {
        query,
        mode,
        semantic_available: mode !== "keyword",
        items:
          query === "no matching lessons"
            ? []
            : [{ content: resultContent, score: 0.02, matched_by: matchedBy }]
      }
    });
  });
}

async function submitSearch(page: Page, query: string) {
  const search = page.getByRole("region", { name: "Find your next technology lesson" });
  await search.getByRole("textbox", { name: "Search learning content" }).fill(query);
  await search.getByRole("button", { name: "Search" }).click();
}

test.beforeEach(async ({ page }) => {
  await mockSearch(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Search", exact: true }).first().click();
});

test("supports hybrid, keyword, and semantic discovery with publisher links", async ({
  page
}) => {
  await submitSearch(page, "practical skills beyond school");
  await expect(page.getByText("keyword + semantic")).toBeVisible();

  const resultLink = page.getByRole("link", {
    name: "Why School Work Is Not Enough for a Techie"
  });
  await expect(resultLink).toHaveAttribute("href", resultContent.canonical_url);
  await expect(resultLink).toHaveAttribute("target", "_blank");

  await page.getByText("Keyword", { exact: true }).click();
  await page
    .getByRole("region", { name: "Find your next technology lesson" })
    .getByRole("button", { name: "Search" })
    .click();
  await expect(page.getByText("keyword", { exact: true })).toBeVisible();

  await page.getByText("Semantic", { exact: true }).click();
  await page
    .getByRole("region", { name: "Find your next technology lesson" })
    .getByRole("button", { name: "Search" })
    .click();
  await expect(page.getByText("semantic", { exact: true })).toBeVisible();
});

test("renders empty and unavailable search states", async ({ page }) => {
  await submitSearch(page, "no matching lessons");
  await expect(page.getByText("No approved learning content matched.")).toBeVisible();

  await submitSearch(page, "service failure");
  await expect(page.getByText("Search is temporarily unavailable.")).toBeVisible();
});
