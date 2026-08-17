import { NextRequest, NextResponse } from "next/server";

import { BACKEND_API_BASE_URL, SESSION_COOKIE_NAME } from "@/lib/auth";

async function proxy(request: NextRequest, method: "GET" | "PUT") {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) return NextResponse.json({ detail: "Sesión no encontrada" }, { status: 401 });
  const query = request.nextUrl.searchParams.toString();
  const response = await fetch(`${BACKEND_API_BASE_URL}/staff/schedules${query ? `?${query}` : ""}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, ...(method === "PUT" ? { "content-type": "application/json" } : {}) },
    body: method === "PUT" ? await request.text() : undefined,
    cache: "no-store",
  });
  return new NextResponse(await response.text(), { status: response.status, headers: { "content-type": response.headers.get("content-type") ?? "application/json" } });
}

export const GET = (request: NextRequest) => proxy(request, "GET");
export const PUT = (request: NextRequest) => proxy(request, "PUT");
