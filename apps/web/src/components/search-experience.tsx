"use client";

import { FormEvent, useState, useTransition } from "react";

import { searchContent, type SearchMode, type SearchResponse } from "@/lib/api";

const modes: Array<{ value: SearchMode; label: string }> = [
  { value: "hybrid", label: "Hybrid" },
  { value: "keyword", label: "Keyword" },
  { value: "semantic", label: "Semantic" }
];

export function SearchExperience({ compact = false }: { compact?: boolean }) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = query.trim();
    if (normalized.length < 2) return;
    setError(null);
    startTransition(async () => {
      try {
        setResult(await searchContent(normalized, mode));
      } catch {
        setResult(null);
        setError("Search is temporarily unavailable.");
      }
    });
  }

  return (
    <section aria-labelledby="search-heading">
      <div className="border-b border-dawn-line bg-white">
        <div className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
          {!compact ? <p className="text-sm font-semibold text-dawn-teal">Edu DawnSynch</p> : null}
          <h1 id="search-heading" className="mt-2 text-3xl font-semibold text-dawn-ink sm:text-4xl">
            Find your next technology lesson
          </h1>
          <form className="mt-7" onSubmit={submit}>
            <div className="flex flex-col gap-3 sm:flex-row">
              <label className="sr-only" htmlFor="learning-search">
                Search learning content
              </label>
              <input
                id="learning-search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Try Python loops, accessible forms, or Kubernetes"
                className="min-h-12 flex-1 rounded border border-slate-300 bg-white px-4 text-base outline-none transition focus:border-dawn-teal focus:ring-2 focus:ring-teal-100"
              />
              <button
                type="submit"
                disabled={isPending || query.trim().length < 2}
                className="min-h-12 rounded bg-dawn-ink px-6 font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
              >
                {isPending ? "Searching..." : "Search"}
              </button>
            </div>
            <fieldset className="mt-4 flex flex-wrap gap-2">
              <legend className="sr-only">Search mode</legend>
              {modes.map((option) => (
                <label key={option.value} className="cursor-pointer">
                  <input
                    className="peer sr-only"
                    type="radio"
                    name="mode"
                    value={option.value}
                    checked={mode === option.value}
                    onChange={() => setMode(option.value)}
                  />
                  <span className="inline-flex rounded border border-dawn-line bg-white px-3 py-2 text-sm font-medium text-slate-600 peer-checked:border-dawn-teal peer-checked:bg-teal-50 peer-checked:text-dawn-teal">
                    {option.label}
                  </span>
                </label>
              ))}
            </fieldset>
          </form>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-5 py-7 sm:px-8">
        {error ? <p className="border-l-4 border-amber-500 bg-amber-50 p-4 text-amber-900">{error}</p> : null}
        {result ? (
          <div>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-dawn-line pb-4">
              <p className="text-sm text-slate-600">
                {result.items.length} results for <strong className="text-dawn-ink">{result.query}</strong>
              </p>
              {result.mode === "hybrid" && !result.semantic_available ? (
                <span className="text-sm font-medium text-amber-700">Keyword fallback active</span>
              ) : null}
            </div>
            {result.items.length ? (
              <ol className="divide-y divide-dawn-line">
                {result.items.map((item) => (
                  <li key={item.content.id} className="py-6">
                    <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase text-slate-500">
                      <span>{item.content.content_type}</span>
                      <span aria-hidden="true">/</span>
                      <span>{item.matched_by.join(" + ")}</span>
                    </div>
                    <h2 className="mt-2 text-xl font-semibold text-dawn-ink">
                      <a
                        className="hover:text-dawn-teal hover:underline"
                        href={item.content.canonical_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {item.content.title}
                      </a>
                    </h2>
                    {item.content.description ? (
                      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                        {item.content.description}
                      </p>
                    ) : null}
                    <p className="mt-3 text-sm text-slate-500">
                      {item.content.author_name ?? "Original publisher"}
                    </p>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="py-12 text-center text-slate-600">No approved learning content matched.</p>
            )}
          </div>
        ) : (
          <div className="grid gap-5 border-t border-dawn-line pt-6 sm:grid-cols-3">
            <p className="text-sm leading-6 text-slate-600">Search only approved, moderated learning sources.</p>
            <p className="text-sm leading-6 text-slate-600">Hybrid mode balances exact terms with semantic relevance.</p>
            <p className="text-sm leading-6 text-slate-600">Every result links to the original publisher.</p>
          </div>
        )}
      </div>
    </section>
  );
}
