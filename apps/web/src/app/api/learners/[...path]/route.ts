import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "@/lib/api";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const upstream = new URL(
    `/api/v1/learners/${path.map(encodeURIComponent).join("/")}`,
    getApiBaseUrl()
  );
  upstream.search = request.nextUrl.search;
  const body = request.method === "GET" || request.method === "DELETE" ? undefined : await request.text();

  try {
    const response = await fetch(upstream, {
      method: request.method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body || undefined,
      cache: "no-store"
    });
    if (response.status === 204) return new NextResponse(null, { status: 204 });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json({ detail: "Learner service is unavailable" }, { status: 503 });
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
