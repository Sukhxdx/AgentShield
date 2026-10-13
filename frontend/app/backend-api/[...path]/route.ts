import { NextRequest, NextResponse } from "next/server";

function upstreamBase() {
  const raw = process.env.API_UPSTREAM_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8741";
  const trimmed = raw.replace(/\/$/, "");
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) return trimmed;
  return `http://${trimmed}`;
}

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const apiKey = process.env.API_KEY || "dev-only-change-me";
  const target = `${upstreamBase()}/${path.join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  headers.set("X-API-Key", apiKey);
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const init: RequestInit = { method: request.method, headers, cache: "no-store" };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.text();
  }
  try {
    const response = await fetch(target, init);
    const body = await response.arrayBuffer();
    return new NextResponse(body, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") || "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "AgentShield API is not reachable. Start it with make dev." },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
