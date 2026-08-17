import { NextRequest, NextResponse } from "next/server";

import { BACKEND_API_BASE_URL, ChangePasswordResponse, SESSION_COOKIE_NAME, resolvePasswordChangeUser } from "@/lib/auth";

export async function POST(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Sesión no encontrada" }, { status: 401 });
  }
  const payload = await request.json();
  const response = await fetch(`${BACKEND_API_BASE_URL}/auth/change-password`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const body = await response.text();
  if (response.ok) {
    const parsed = JSON.parse(body) as ChangePasswordResponse;
    const nextResponse = NextResponse.json(resolvePasswordChangeUser(parsed));
    const refreshedToken = response.headers.get("X-Modeloasist-Access-Token");
    if (refreshedToken) {
      nextResponse.cookies.set(SESSION_COOKIE_NAME, refreshedToken, {
        httpOnly: true,
        sameSite: "lax",
        secure: false,
        path: "/",
        maxAge: 60 * 60 * 8,
      });
    }
    return nextResponse;
  }
  return new NextResponse(body, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
  });
}