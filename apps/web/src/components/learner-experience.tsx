"use client";

import {
  Bookmark,
  BookmarkCheck,
  Compass,
  ExternalLink,
  Search,
  SlidersHorizontal,
  X
} from "lucide-react";
import { useCallback, useEffect, useState, useTransition } from "react";

import { SearchExperience } from "@/components/search-experience";
import {
  createLearner,
  dismissRecommendation,
  getLearner,
  getRecommendations,
  LearnerApiError,
  recordEngagement,
  setBookmark,
  updateLearner,
  type LearnerPreferences,
  type LearnerProfile,
  type RecommendationItem,
  type RecommendationResponse,
  type SkillLevel
} from "@/lib/api";

const STORAGE_KEY = "edu-dawnsynch:learner:v1";
const careers = [
  "software developer",
  "data analyst",
  "security analyst",
  "cloud engineer",
  "product designer"
];
const domains = [
  "python",
  "web development",
  "cybersecurity",
  "cloud computing",
  "data analytics",
  "artificial intelligence"
];
const levels: SkillLevel[] = ["beginner", "intermediate", "advanced"];
const componentLabels: Record<string, string> = {
  career_relevance: "Career relevance",
  domain_relevance: "Domain relevance",
  skill_level_fit: "Level fit",
  quality: "Quality",
  freshness: "Freshness",
  interactions: "Your signals"
};

type View = "feed" | "search";
type SetupProps = {
  initial?: LearnerPreferences;
  saving: boolean;
  onCancel?: () => void;
  onSubmit: (preferences: LearnerPreferences) => void;
};

function titleCase(value: string) {
  return value.replace(/\b\w/g, (character) => character.toUpperCase());
}

function toggle(values: string[], value: string) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function PreferenceSetup({ initial, saving, onCancel, onSubmit }: SetupProps) {
  const [careerPreferences, setCareerPreferences] = useState(initial?.career_preferences ?? []);
  const [technologyDomains, setTechnologyDomains] = useState(initial?.technology_domains ?? []);
  const [skillLevel, setSkillLevel] = useState<SkillLevel>(initial?.skill_level ?? "beginner");
  const hasSelection = careerPreferences.length > 0 || technologyDomains.length > 0;

  return (
    <form
      className="mx-auto max-w-3xl"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit({
          career_preferences: careerPreferences,
          technology_domains: technologyDomains,
          skill_level: skillLevel
        });
      }}
    >
      <div className="border-b border-dawn-line pb-5">
        <p className="text-sm font-semibold text-dawn-teal">Your learning profile</p>
        <h1 className="mt-2 text-3xl font-semibold text-dawn-ink sm:text-4xl">
          Shape your technology feed
        </h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
          Choose where you are heading and what you want to learn now.
        </p>
      </div>

      <fieldset className="py-6">
        <legend className="text-base font-semibold text-dawn-ink">Career direction</legend>
        <div className="mt-3 flex flex-wrap gap-2">
          {careers.map((career) => (
            <label key={career} className="cursor-pointer">
              <input
                className="peer sr-only"
                type="checkbox"
                checked={careerPreferences.includes(career)}
                onChange={() => setCareerPreferences((current) => toggle(current, career))}
              />
              <span className="inline-flex min-h-10 items-center rounded border border-dawn-line bg-white px-3 text-sm font-medium text-slate-600 transition peer-checked:border-dawn-teal peer-checked:bg-teal-50 peer-checked:text-dawn-teal peer-focus-visible:ring-2 peer-focus-visible:ring-teal-200">
                {titleCase(career)}
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="border-t border-dawn-line py-6">
        <legend className="pt-6 text-base font-semibold text-dawn-ink">Technology domains</legend>
        <div className="mt-3 flex flex-wrap gap-2">
          {domains.map((domain) => (
            <label key={domain} className="cursor-pointer">
              <input
                className="peer sr-only"
                type="checkbox"
                checked={technologyDomains.includes(domain)}
                onChange={() => setTechnologyDomains((current) => toggle(current, domain))}
              />
              <span className="inline-flex min-h-10 items-center rounded border border-dawn-line bg-white px-3 text-sm font-medium text-slate-600 transition peer-checked:border-dawn-teal peer-checked:bg-teal-50 peer-checked:text-dawn-teal peer-focus-visible:ring-2 peer-focus-visible:ring-teal-200">
                {titleCase(domain)}
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="border-t border-dawn-line py-6">
        <legend className="pt-6 text-base font-semibold text-dawn-ink">Current skill level</legend>
        <div className="mt-3 grid max-w-lg grid-cols-3 overflow-hidden rounded border border-dawn-line bg-white">
          {levels.map((level) => (
            <label key={level} className="cursor-pointer border-r border-dawn-line last:border-r-0">
              <input
                className="peer sr-only"
                type="radio"
                name="skill-level"
                checked={skillLevel === level}
                onChange={() => setSkillLevel(level)}
              />
              <span className="flex min-h-11 items-center justify-center px-2 text-sm font-medium text-slate-600 peer-checked:bg-dawn-ink peer-checked:text-white peer-focus-visible:ring-2 peer-focus-visible:ring-inset peer-focus-visible:ring-teal-200">
                {titleCase(level)}
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="flex flex-wrap gap-3 border-t border-dawn-line pt-6">
        <button
          type="submit"
          disabled={!hasSelection || saving}
          className="min-h-11 rounded bg-dawn-ink px-5 font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {saving ? "Saving..." : initial ? "Update feed" : "Create my feed"}
        </button>
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="min-h-11 rounded border border-dawn-line bg-white px-5 font-semibold text-slate-700 hover:border-slate-400"
          >
            Cancel
          </button>
        ) : null}
      </div>
    </form>
  );
}

function RecommendationRow({
  item,
  bookmarked,
  busy,
  onBookmark,
  onDismiss,
  onOpen
}: {
  item: RecommendationItem;
  bookmarked: boolean;
  busy: boolean;
  onBookmark: () => void;
  onDismiss: () => void;
  onOpen: () => void;
}) {
  const match = Math.round(item.score * 100);
  const matched = [...item.explanation.matched_careers, ...item.explanation.matched_domains];

  return (
    <li className="recommendation-row py-6">
      <article>
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase text-slate-500">
              <span>{item.content.content_type}</span>
              <span aria-hidden="true">/</span>
              <span className="text-dawn-teal">{match}% match</span>
              <span aria-hidden="true">/</span>
              <span>{item.content.source_name}</span>
            </div>
            <h2 className="mt-2 text-xl font-semibold text-dawn-ink">
              <a
                className="inline-flex items-start gap-2 hover:text-dawn-teal hover:underline"
                href={item.content.canonical_url}
                target="_blank"
                rel="noreferrer"
                onClick={onOpen}
              >
                <span>{item.content.title}</span>
                <ExternalLink className="mt-1 h-4 w-4 shrink-0" aria-hidden="true" />
              </a>
            </h2>
          </div>
          <div className="flex shrink-0 gap-1">
            <button
              type="button"
              aria-label={bookmarked ? "Remove bookmark" : "Bookmark lesson"}
              title={bookmarked ? "Remove bookmark" : "Bookmark lesson"}
              disabled={busy}
              onClick={onBookmark}
              className="inline-flex h-10 w-10 items-center justify-center rounded border border-dawn-line bg-white text-slate-600 hover:border-dawn-teal hover:text-dawn-teal disabled:opacity-50"
            >
              {bookmarked ? (
                <BookmarkCheck className="h-5 w-5" aria-hidden="true" />
              ) : (
                <Bookmark className="h-5 w-5" aria-hidden="true" />
              )}
            </button>
            <button
              type="button"
              aria-label="Dismiss lesson"
              title="Dismiss lesson"
              disabled={busy}
              onClick={onDismiss}
              className="inline-flex h-10 w-10 items-center justify-center rounded border border-dawn-line bg-white text-slate-600 hover:border-rose-300 hover:text-rose-700 disabled:opacity-50"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
        </div>

        {item.content.description ? (
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{item.content.description}</p>
        ) : null}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {matched.map((label) => (
            <span key={label} className="rounded bg-white px-2 py-1 text-xs font-medium text-slate-600">
              {titleCase(label)}
            </span>
          ))}
          <details className="group text-sm text-slate-600">
            <summary className="cursor-pointer font-medium text-dawn-teal hover:underline">Why this?</summary>
            <div className="mt-3 grid gap-x-8 gap-y-2 sm:grid-cols-2">
              {Object.entries(item.explanation.components).map(([name, component]) => (
                <div key={name} className="flex min-w-0 items-center justify-between gap-4">
                  <span>{componentLabels[name] ?? titleCase(name)}</span>
                  <span className="font-semibold text-dawn-ink">{Math.round(component.value * 100)}%</span>
                </div>
              ))}
            </div>
          </details>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          {item.content.attribution ?? item.content.source_name}
        </p>
      </article>
    </li>
  );
}

export function LearnerExperience() {
  const [view, setView] = useState<View>("feed");
  const [profile, setProfile] = useState<LearnerProfile | null>(null);
  const [feed, setFeed] = useState<RecommendationResponse | null>(null);
  const [setup, setSetup] = useState(false);
  const [loading, setLoading] = useState(true);
  const [restoreFailed, setRestoreFailed] = useState(false);
  const [restoreNonce, setRestoreNonce] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [bookmarked, setBookmarked] = useState<Set<number>>(() => new Set());
  const [busyIds, setBusyIds] = useState<Set<number>>(() => new Set());
  const [isPending, startTransition] = useTransition();

  const applyFeed = useCallback((next: RecommendationResponse) => {
    setFeed(next);
    setBookmarked(
      new Set(
        next.items
          .filter((item) => item.explanation.interaction_signals.includes("bookmarked"))
          .map((item) => item.content.id)
      )
    );
  }, []);

  useEffect(() => {
    let active = true;
    async function restore() {
      setLoading(true);
      setRestoreFailed(false);
      setError(null);
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (!stored) {
        if (active) setLoading(false);
        return;
      }
      try {
        const parsed = JSON.parse(stored) as { version?: number; learnerId?: string };
        if (parsed.version !== 1 || !parsed.learnerId) throw new Error("Invalid learner record");
        const [restoredProfile, recommendations] = await Promise.all([
          getLearner(parsed.learnerId),
          getRecommendations(parsed.learnerId)
        ]);
        if (!active) return;
        setProfile(restoredProfile);
        applyFeed(recommendations);
      } catch (restoreError) {
        if (restoreError instanceof LearnerApiError && restoreError.status !== 404) {
          if (active) {
            setRestoreFailed(true);
            setError("Your saved feed is temporarily unavailable.");
          }
        } else {
          window.localStorage.removeItem(STORAGE_KEY);
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    void restore();
    return () => {
      active = false;
    };
  }, [applyFeed, restoreNonce]);

  function savePreferences(preferences: LearnerPreferences) {
    setError(null);
    startTransition(async () => {
      try {
        const saved = profile
          ? await updateLearner(profile.id, preferences)
          : await createLearner(preferences);
        window.localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({ version: 1, learnerId: saved.id })
        );
        const recommendations = await getRecommendations(saved.id);
        setProfile(saved);
        applyFeed(recommendations);
        setSetup(false);
      } catch {
        setError("Your learning profile could not be saved. Please try again.");
      }
    });
  }

  function mutateItem(contentId: number, action: () => Promise<void>, remove: boolean) {
    if (!profile) return;
    setError(null);
    setBusyIds((current) => new Set(current).add(contentId));
    if (remove) {
      setFeed((current) =>
        current ? { ...current, items: current.items.filter((item) => item.content.id !== contentId) } : current
      );
    }
    void action()
      .then(() => getRecommendations(profile.id))
      .then(applyFeed)
      .catch(async () => {
        setError("That change could not be saved. Please try again.");
        try {
          applyFeed(await getRecommendations(profile.id));
        } catch {
          // Keep the error visible; retrying the feed happens on the next action or reload.
        }
      })
      .finally(() =>
        setBusyIds((current) => {
          const next = new Set(current);
          next.delete(contentId);
          return next;
        })
      );
  }

  function toggleBookmark(contentId: number) {
    if (!profile) return;
    const enabled = !bookmarked.has(contentId);
    setBookmarked((current) => {
      const next = new Set(current);
      if (enabled) next.add(contentId);
      else next.delete(contentId);
      return next;
    });
    mutateItem(contentId, () => setBookmark(profile.id, contentId, enabled), false);
  }

  function loadMore() {
    if (!profile || !feed?.next_cursor) return;
    startTransition(async () => {
      try {
        const next = await getRecommendations(profile.id, feed.next_cursor ?? undefined);
        setFeed((current) =>
          current
            ? { ...next, items: [...current.items, ...next.items] }
            : next
        );
      } catch {
        setError("More recommendations could not be loaded.");
      }
    });
  }

  function recordOpen(contentId: number) {
    if (!profile) return;
    void recordEngagement(profile.id, contentId, "click")
      .then(() => getRecommendations(profile.id))
      .then(applyFeed)
      .catch(() => undefined);
  }

  const needsSetup = !profile || setup;

  return (
    <section>
      <header className="border-b border-dawn-line bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <button
            type="button"
            className="text-left text-sm font-bold text-dawn-teal"
            onClick={() => setView("feed")}
          >
            Edu DawnSynch
          </button>
          <nav className="flex rounded border border-dawn-line bg-dawn-mist p-1" aria-label="Learning views">
            <button
              type="button"
              onClick={() => setView("feed")}
              className={`inline-flex min-h-9 items-center gap-2 rounded px-3 text-sm font-semibold ${
                view === "feed" ? "bg-white text-dawn-ink shadow-sm" : "text-slate-600"
              }`}
            >
              <Compass className="h-4 w-4" aria-hidden="true" />
              For you
            </button>
            <button
              type="button"
              onClick={() => setView("search")}
              className={`inline-flex min-h-9 items-center gap-2 rounded px-3 text-sm font-semibold ${
                view === "search" ? "bg-white text-dawn-ink shadow-sm" : "text-slate-600"
              }`}
            >
              <Search className="h-4 w-4" aria-hidden="true" />
              Search
            </button>
          </nav>
        </div>
      </header>

      {view === "search" ? (
        <SearchExperience compact />
      ) : (
        <div className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
          {loading ? <p className="py-16 text-center text-slate-600">Loading your learning feed...</p> : null}
          {!loading && restoreFailed ? (
            <div className="mx-auto max-w-xl py-16 text-center">
              <h1 className="text-3xl font-semibold text-dawn-ink">Your feed is temporarily unavailable</h1>
              <p className="mt-3 text-slate-600">Your learning profile is still saved on this device.</p>
              <button
                type="button"
                onClick={() => setRestoreNonce((current) => current + 1)}
                className="mt-6 min-h-11 rounded bg-dawn-ink px-5 font-semibold text-white hover:bg-slate-700"
              >
                Try again
              </button>
            </div>
          ) : null}
          {!loading && !restoreFailed && needsSetup ? (
            <PreferenceSetup
              key={profile?.recommendation_version ?? "new"}
              initial={profile ?? undefined}
              saving={isPending}
              onCancel={profile ? () => setSetup(false) : undefined}
              onSubmit={savePreferences}
            />
          ) : null}
          {!loading && !restoreFailed && profile && !setup ? (
            <div>
              <div className="flex flex-wrap items-end justify-between gap-4 border-b border-dawn-line pb-5">
                <div>
                  <p className="text-sm font-semibold text-dawn-teal">Personalized learning feed</p>
                  <h1 className="mt-2 text-3xl font-semibold text-dawn-ink sm:text-4xl">Built around your next step</h1>
                  <p className="mt-3 text-sm text-slate-600">
                    {profile.skill_level.charAt(0).toUpperCase() + profile.skill_level.slice(1)} · {[
                      ...profile.career_preferences,
                      ...profile.technology_domains
                    ]
                      .slice(0, 3)
                      .map(titleCase)
                      .join(" · ")}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSetup(true)}
                  className="inline-flex min-h-10 items-center gap-2 rounded border border-dawn-line bg-white px-3 text-sm font-semibold text-slate-700 hover:border-dawn-teal hover:text-dawn-teal"
                >
                  <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
                  Edit preferences
                </button>
              </div>

              {error ? <p className="mt-5 border-l-4 border-amber-500 bg-amber-50 p-4 text-amber-900">{error}</p> : null}
              {feed?.items.length ? (
                <ol className="divide-y divide-dawn-line">
                  {feed.items.map((item) => (
                    <RecommendationRow
                      key={item.content.id}
                      item={item}
                      bookmarked={bookmarked.has(item.content.id)}
                      busy={busyIds.has(item.content.id)}
                      onBookmark={() => toggleBookmark(item.content.id)}
                      onDismiss={() =>
                        mutateItem(
                          item.content.id,
                          () => dismissRecommendation(profile.id, item.content.id),
                          true
                        )
                      }
                      onOpen={() => recordOpen(item.content.id)}
                    />
                  ))}
                </ol>
              ) : (
                <p className="py-16 text-center text-slate-600">No recommendations are available yet.</p>
              )}
              {feed?.next_cursor ? (
                <div className="border-t border-dawn-line pt-6 text-center">
                  <button
                    type="button"
                    disabled={isPending}
                    onClick={loadMore}
                    className="min-h-11 rounded border border-dawn-line bg-white px-5 font-semibold text-slate-700 hover:border-dawn-teal hover:text-dawn-teal disabled:opacity-50"
                  >
                    {isPending ? "Loading..." : "Load more"}
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
          {error && needsSetup && !restoreFailed ? <p className="mt-5 border-l-4 border-amber-500 bg-amber-50 p-4 text-amber-900">{error}</p> : null}
        </div>
      )}
    </section>
  );
}
