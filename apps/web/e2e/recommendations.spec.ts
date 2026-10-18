import { expect, test, type Page } from "@playwright/test";

const learnerId = "4d8c9e98-ea11-4ef1-aea1-0388ccbd52d3";
const profile = {
  id: learnerId,
  career_preferences: ["software developer"],
  technology_domains: ["python"],
  skill_level: "beginner",
  recommendation_version: 1,
  created_at: "2026-10-16T10:00:00Z",
  updated_at: "2026-10-16T10:00:00Z"
};
const recommendation = {
  content: {
    id: 62,
    source_id: 28,
    source_name: "Edu DawnSynch Blog",
    attribution: "Edu DawnSynch Blog",
    canonical_url: "https://blog.edu.dawnsynch.co.ke/python",
    title: "Python foundations for new developers",
    description: "Build useful programming foundations through practical work.",
    content_type: "article",
    author_name: "Alex",
    language_code: "en",
    thumbnail_url: null,
    duration_seconds: null,
    published_at: "2026-10-10T10:00:00Z"
  },
  score: 0.88,
  explanation: {
    components: {
      career_relevance: { weight: 0.25, value: 1, contribution: 0.25, reason: "Career match" },
      domain_relevance: { weight: 0.2, value: 1, contribution: 0.2, reason: "Domain match" },
      skill_level_fit: { weight: 0.15, value: 1, contribution: 0.15, reason: "Level match" },
      quality: { weight: 0.2, value: 0.85, contribution: 0.17, reason: "Quality" },
      freshness: { weight: 0.1, value: 1, contribution: 0.1, reason: "Fresh" },
      interactions: { weight: 0.1, value: 0.25, contribution: 0.025, reason: "Signals" }
    },
    matched_careers: ["software developer"],
    matched_domains: ["python"],
    interaction_signals: [] as string[]
  }
};

async function mockLearnerApi(page: Page) {
  let created = false;
  let bookmarked = false;
  let dismissed = false;
  await page.route("**/api/learners**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (request.method() === "POST" && path === "/api/learners") {
      created = true;
      await route.fulfill({ status: 201, json: profile });
      return;
    }
    if (request.method() === "GET" && path.endsWith("/preferences")) {
      await route.fulfill({ status: created ? 200 : 404, json: created ? profile : { detail: "not found" } });
      return;
    }
    if (request.method() === "PUT" && path.includes("/bookmarks/")) {
      bookmarked = true;
      await route.fulfill({ status: 200, json: { learner_id: learnerId, content_id: 62, bookmarked: true, dismissed: false } });
      return;
    }
    if (request.method() === "PUT" && path.includes("/dismissals/")) {
      dismissed = true;
      await route.fulfill({ status: 200, json: { learner_id: learnerId, content_id: 62, bookmarked: false, dismissed: true } });
      return;
    }
    if (request.method() === "POST" && path.endsWith("/engagement-events")) {
      await route.fulfill({ status: 201, json: { id: 1 } });
      return;
    }
    if (request.method() === "GET" && path.endsWith("/recommendations")) {
      const item = {
        ...recommendation,
        explanation: {
          ...recommendation.explanation,
          interaction_signals: bookmarked ? ["bookmarked"] : []
        }
      };
      await route.fulfill({
        status: 200,
        json: {
          learner_id: learnerId,
          recommendation_version: bookmarked || dismissed ? 2 : 1,
          cold_start: false,
          diversity_applied: false,
          items: dismissed ? [] : [item],
          next_cursor: null
        }
      });
      return;
    }
    await route.fulfill({ status: 404, json: { detail: "Unhandled learner route" } });
  });
}

test("onboards a learner and persists the personalized feed across reload", async ({ page }) => {
  await mockLearnerApi(page);
  await page.goto("/");

  await page.getByText("Software Developer", { exact: true }).click();
  await page.getByText("Python", { exact: true }).click();
  await page.getByRole("button", { name: "Create my feed" }).click();

  await expect(page.getByRole("heading", { name: "Built around your next step" })).toBeVisible();
  await expect(page.getByText(recommendation.content.title)).toBeVisible();
  await expect(page.getByText("88% match")).toBeVisible();

  await page.reload();
  await expect(page.getByText(recommendation.content.title)).toBeVisible();
  const stored = await page.evaluate(() => window.localStorage.getItem("edu-dawnsynch:learner:v1"));
  expect(stored).toContain(learnerId);
});

test("bookmarks, explains, and dismisses a recommendation", async ({ page }) => {
  await mockLearnerApi(page);
  await page.goto("/");
  await page.getByText("Software Developer", { exact: true }).click();
  await page.getByText("Python", { exact: true }).click();
  await page.getByRole("button", { name: "Create my feed" }).click();

  await page.getByText("Why this?").click();
  await expect(page.getByText("Career relevance")).toBeVisible();

  await page.getByRole("button", { name: "Bookmark lesson" }).click();
  await expect(page.getByRole("button", { name: "Remove bookmark" })).toBeVisible();

  await page.getByRole("button", { name: "Dismiss lesson" }).click();
  await expect(page.getByText(recommendation.content.title)).not.toBeVisible();
  await expect(page.getByText("No recommendations are available yet.")).toBeVisible();
});
