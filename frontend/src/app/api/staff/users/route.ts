import { NextRequest, NextResponse } from "next/server";

import { BACKEND_API_BASE_URL, SESSION_COOKIE_NAME } from "@/lib/auth";

function buildHeaders(token: string) {
  return {
    Authorization: `Bearer ${token}`,
    "content-type": "application/json",
  };
}

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Sesión no encontrada" }, { status: 401 });
  }
  const response = await fetch(`${BACKEND_API_BASE_URL}/staff/users`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
  });
}

export async function POST(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Sesión no encontrada" }, { status: 401 });
  }
  const payload = await request.json();
  const response = await fetch(`${BACKEND_API_BASE_URL}/staff/users`, {
    method: "POST",
    headers: buildHeaders(token),
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
  });
}