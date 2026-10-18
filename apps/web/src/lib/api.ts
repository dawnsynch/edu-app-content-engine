export type ApiHealth = {
  status: "ok";
  service: string;
  environment: string;
};

export type SearchMode = "keyword" | "semantic" | "hybrid";

export type SearchItem = {
  content: {
    id: number;
    source_id: number;
    canonical_url: string;
    title: string;
    description: string | null;
    content_type: string;
    author_name: string | null;
    language_code: string | null;
    thumbnail_url: string | null;
    duration_seconds: number | null;
    published_at: string | null;
  };
  score: number;
  matched_by: string[];
};

export type SearchResponse = {
  query: string;
  mode: SearchMode;
  semantic_available: boolean;
  items: SearchItem[];
};

export type SkillLevel = "beginner" | "intermediate" | "advanced";

export type LearnerProfile = {
  id: string;
  career_preferences: string[];
  technology_domains: string[];
  skill_level: SkillLevel;
  recommendation_version: number;
  created_at: string;
  updated_at: string;
};

export type LearnerPreferences = Pick<
  LearnerProfile,
  "career_preferences" | "technology_domains" | "skill_level"
>;

export type RecommendationContent = {
  id: number;
  source_id: number;
  source_name: string;
  attribution: string | null;
  canonical_url: string;
  title: string;
  description: string | null;
  content_type: string;
  author_name: string | null;
  language_code: string | null;
  thumbnail_url: string | null;
  duration_seconds: number | null;
  published_at: string | null;
};

export type ScoreComponent = {
  weight: number;
  value: number;
  contribution: number;
  reason: string;
};

export type RecommendationItem = {
  content: RecommendationContent;
  score: number;
  explanation: {
    components: Record<string, ScoreComponent>;
    matched_careers: string[];
    matched_domains: string[];
    interaction_signals: string[];
  };
};

export type RecommendationResponse = {
  learner_id: string;
  recommendation_version: number;
  cold_start: boolean;
  diversity_applied: boolean;
  items: RecommendationItem[];
  next_cursor: string | null;
};

export class LearnerApiError extends Error {
  constructor(public readonly status: number) {
    super(`Learner request failed with status ${status}`);
  }
}

const fallbackApiBaseUrl = "http://localhost:8010";

export function getApiBaseUrl(): string {
  return process.env.API_INTERNAL_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? fallbackApiBaseUrl;
}

export async function searchContent(query: string, mode: SearchMode): Promise<SearchResponse> {
  const parameters = new URLSearchParams({ q: query, mode });
  const response = await fetch(`/api/search?${parameters.toString()}`, {
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Search failed with status ${response.status}`);
  }
  return (await response.json()) as SearchResponse;
}

async function learnerRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/learners${path}`, {
    cache: "no-store",
    ...init,
    headers: init?.body
      ? { "Content-Type": "application/json", ...init.headers }
      : init?.headers
  });
  if (!response.ok) {
    throw new LearnerApiError(response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function createLearner(preferences: LearnerPreferences): Promise<LearnerProfile> {
  return learnerRequest<LearnerProfile>("", {
    method: "POST",
    body: JSON.stringify(preferences)
  });
}

export function getLearner(learnerId: string): Promise<LearnerProfile> {
  return learnerRequest<LearnerProfile>(`/${learnerId}/preferences`);
}

export function updateLearner(
  learnerId: string,
  preferences: LearnerPreferences
): Promise<LearnerProfile> {
  return learnerRequest<LearnerProfile>(`/${learnerId}/preferences`, {
    method: "PATCH",
    body: JSON.stringify(preferences)
  });
}

export function getRecommendations(
  learnerId: string,
  cursor?: string
): Promise<RecommendationResponse> {
  const parameters = new URLSearchParams({ limit: "10" });
  if (cursor) parameters.set("cursor", cursor);
  return learnerRequest<RecommendationResponse>(
    `/${learnerId}/recommendations?${parameters.toString()}`
  );
}

export async function setBookmark(
  learnerId: string,
  contentId: number,
  enabled: boolean
): Promise<void> {
  await learnerRequest(`/${learnerId}/bookmarks/${contentId}`, {
    method: enabled ? "PUT" : "DELETE"
  });
}

// General Comment


export async function dismissRecommendation(
  learnerId: string,
  contentId: number
): Promise<void> {
  await learnerRequest(`/${learnerId}/dismissals/${contentId}`, { method: "PUT" });
}

export async function recordEngagement(
  learnerId: string,
  contentId: number,
  eventType: "view" | "click" | "start" | "complete"
): Promise<void> {
  await learnerRequest(`/${learnerId}/engagement-events`, {
    method: "POST",
    body: JSON.stringify({ content_id: contentId, event_type: eventType })
  });
}

export async function fetchApiHealth(): Promise<ApiHealth> {
  const response = await fetch(`${getApiBaseUrl()}/health/live`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`API health check failed with status ${response.status}`);
  }

  return (await response.json()) as ApiHealth;
}

