import { NextRequest, NextResponse } from "next/server";

import { BACKEND_API_BASE_URL, SESSION_COOKIE_NAME } from "@/lib/auth";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Sesión no encontrada" }, { status: 401 });
  }

  const searchParams = request.nextUrl.searchParams.toString();
  const targetUrl = `${BACKEND_API_BASE_URL}/staff/mobile/daily${searchParams ? `?${searchParams}` : ""}`;
  const response = await fetch(targetUrl, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
  });
}
