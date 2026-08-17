import { NextRequest, NextResponse } from "next/server";

import { BACKEND_API_BASE_URL, SESSION_COOKIE_NAME } from "@/lib/auth";
import { getSessionUserFromToken } from "@/lib/server-auth-token";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Sesión no encontrada" }, { status: 401 });
  }

  const localUser = getSessionUserFromToken(token);
  if (localUser) {
    return NextResponse.json(localUser);
  }

  const response = await fetch(`${BACKEND_API_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
  });
}