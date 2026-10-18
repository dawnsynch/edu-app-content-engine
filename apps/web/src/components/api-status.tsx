import React from "react";

import type { ApiHealth } from "@/lib/api";

type ApiStatusProps = {
  health: ApiHealth | null;
};

export function ApiStatus({ health }: ApiStatusProps) {
  const isOnline = health?.status === "ok";

  return (
    <section className="rounded border border-dawn-line bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-dawn-ink">API connection</h2>
          <p className="mt-1 text-sm text-slate-600">
            {isOnline ? "FastAPI health endpoint is reachable." : "API health is unavailable."}
          </p>
        </div>
        <span
          className={`inline-flex items-center rounded px-3 py-1 text-sm font-medium ${
            isOnline ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
          }`}
        >
          {isOnline ? "Online" : "Pending"}
        </span>
      </div>
      {health ? (
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="font-medium text-slate-500">Service</dt>
            <dd className="mt-1 text-dawn-ink">{health.service}</dd>
          </div>
          <div>
            <dt className="font-medium text-slate-500">Environment</dt>
            <dd className="mt-1 text-dawn-ink">{health.environment}</dd>
          </div>
        </dl>
      ) : null}
    </section>
  );
}

