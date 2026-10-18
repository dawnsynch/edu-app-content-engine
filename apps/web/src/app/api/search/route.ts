import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "@/lib/api";

export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams.get("q") ?? "";
  const mode = request.nextUrl.searchParams.get("mode") ?? "hybrid";
  const upstream = new URL("/api/v1/search", getApiBaseUrl());
  upstream.searchParams.set("q", query);
  upstream.searchParams.set("mode", mode);

  try {
    const response = await fetch(upstream, { cache: "no-store" });
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json({ detail: "Search service is unavailable" }, { status: 503 });
  }
}
