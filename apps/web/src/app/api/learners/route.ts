import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "@/lib/api";

export async function POST(request: NextRequest) {
  const upstream = new URL("/api/v1/learners", getApiBaseUrl());
  try {
    const response = await fetch(upstream, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await request.text(),
      cache: "no-store"
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json({ detail: "Learner service is unavailable" }, { status: 503 });
  }
}

// Added this comment