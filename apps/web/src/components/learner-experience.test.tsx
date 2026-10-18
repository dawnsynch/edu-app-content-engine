import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LearnerExperience } from "@/components/learner-experience";
import {
  createLearner,
  dismissRecommendation,
  getLearner,
  getRecommendations,
  LearnerApiError,
  setBookmark
} from "@/lib/api";

vi.mock("@/lib/api", () => ({
  createLearner: vi.fn(),
  dismissRecommendation: vi.fn(),
  getLearner: vi.fn(),
  getRecommendations: vi.fn(),
  LearnerApiError: class extends Error {
    constructor(public readonly status: number) {
      super(`Status ${status}`);
    }
  },
  recordEngagement: vi.fn(),
  searchContent: vi.fn(),
  setBookmark: vi.fn(),
  updateLearner: vi.fn()
}));

const profile = {
  id: "learner-1",
  career_preferences: ["software developer"],
  technology_domains: ["python"],
  skill_level: "beginner" as const,
  recommendation_version: 1,
  created_at: "2026-10-16T10:00:00Z",
  updated_at: "2026-10-16T10:00:00Z"
};

const item = {
  content: {
    id: 62,
    source_id: 28,
    source_name: "Edu DawnSynch Blog",
    attribution: "Edu DawnSynch Blog",
    canonical_url: "https://blog.edu.dawnsynch.co.ke/python",
    title: "Python foundations for new developers",
    description: "Build useful programming foundations.",
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
      career_relevance: {
        weight: 0.25,
        value: 1,
        contribution: 0.25,
        reason: "Matched learner career preferences."
      }
    },
    matched_careers: ["software developer"],
    matched_domains: ["python"],
    interaction_signals: [] as string[]
  }
};

function recommendationResponse(items = [item]) {
  return {
    learner_id: profile.id,
    recommendation_version: 1,
    cold_start: false,
    diversity_applied: false,
    items,
    next_cursor: null
  };
}

describe("LearnerExperience", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.mocked(createLearner).mockReset();
    vi.mocked(getLearner).mockReset();
    vi.mocked(getRecommendations).mockReset();
    vi.mocked(setBookmark).mockReset();
    vi.mocked(dismissRecommendation).mockReset();
  });

  it("creates a profile and supports bookmark and dismissal controls", async () => {
    vi.mocked(createLearner).mockResolvedValue(profile);
    vi.mocked(getRecommendations)
      .mockResolvedValueOnce(recommendationResponse())
      .mockResolvedValueOnce({
        ...recommendationResponse(),
        items: [
          {
            ...item,
            explanation: {
              ...item.explanation,
              interaction_signals: ["bookmarked"]
            }
          }
        ]
      })
      .mockResolvedValueOnce(recommendationResponse([]));
    vi.mocked(setBookmark).mockResolvedValue();
    vi.mocked(dismissRecommendation).mockResolvedValue();

    render(<LearnerExperience />);

    expect(await screen.findByRole("heading", { name: "Shape your technology feed" })).toBeVisible();
    fireEvent.click(screen.getByRole("checkbox", { name: "Software Developer" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Python" }));
    fireEvent.click(screen.getByRole("button", { name: "Create my feed" }));

    expect(await screen.findByText(item.content.title)).toBeVisible();
    expect(createLearner).toHaveBeenCalledWith({
      career_preferences: ["software developer"],
      technology_domains: ["python"],
      skill_level: "beginner"
    });

    fireEvent.click(screen.getByRole("button", { name: "Bookmark lesson" }));
    await waitFor(() => expect(setBookmark).toHaveBeenCalledWith(profile.id, 62, true));
    expect(await screen.findByRole("button", { name: "Remove bookmark" })).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Dismiss lesson" }));
    await waitFor(() => expect(dismissRecommendation).toHaveBeenCalledWith(profile.id, 62));
    await waitFor(() => expect(screen.queryByText(item.content.title)).not.toBeInTheDocument());
  });

  it("restores the anonymous learner profile from versioned local storage", async () => {
    window.localStorage.setItem(
      "edu-dawnsynch:learner:v1",
      JSON.stringify({ version: 1, learnerId: profile.id })
    );
    vi.mocked(getLearner).mockResolvedValue(profile);
    vi.mocked(getRecommendations).mockResolvedValue(recommendationResponse());

    render(<LearnerExperience />);

    expect(await screen.findByText(item.content.title)).toBeVisible();
    expect(getLearner).toHaveBeenCalledWith(profile.id);
    expect(getRecommendations).toHaveBeenCalledWith(profile.id);
  });

  it("preserves the learner identifier during a temporary API outage", async () => {
    const stored = JSON.stringify({ version: 1, learnerId: profile.id });
    window.localStorage.setItem("edu-dawnsynch:learner:v1", stored);
    vi.mocked(getLearner).mockRejectedValue(new LearnerApiError(503));
    vi.mocked(getRecommendations).mockRejectedValue(new LearnerApiError(503));

    render(<LearnerExperience />);

    expect(
      await screen.findByRole("heading", { name: "Your feed is temporarily unavailable" })
    ).toBeVisible();
    expect(window.localStorage.getItem("edu-dawnsynch:learner:v1")).toBe(stored);
    expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
  });
});
