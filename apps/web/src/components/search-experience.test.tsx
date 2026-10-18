import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SearchExperience } from "@/components/search-experience";
import { searchContent } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  searchContent: vi.fn()
}));

const mockedSearch = vi.mocked(searchContent);

describe("SearchExperience", () => {
  beforeEach(() => mockedSearch.mockReset());

  it("runs hybrid search and renders approved results", async () => {
    mockedSearch.mockResolvedValue({
      query: "python loops",
      mode: "hybrid",
      semantic_available: true,
      items: [
        {
          content: {
            id: 1,
            source_id: 2,
            canonical_url: "https://example.test/python",
            title: "Python loops",
            description: "Practice iteration with short exercises.",
            content_type: "course",
            author_name: "Example Academy",
            language_code: "en",
            thumbnail_url: null,
            duration_seconds: null,
            published_at: null
          },
          score: 0.02,
          matched_by: ["keyword", "semantic"]
        }
      ]
    });
    render(<SearchExperience />);

    fireEvent.change(screen.getByLabelText("Search learning content"), {
      target: { value: "python loops" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => expect(mockedSearch).toHaveBeenCalledWith("python loops", "hybrid"));
    expect(await screen.findByRole("link", { name: "Python loops" })).toBeInTheDocument();
  });
});
