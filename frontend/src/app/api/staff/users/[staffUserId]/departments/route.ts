import { NextRequest, NextResponse } from "next/server";

import { BACKEND_API_BASE_URL, SESSION_COOKIE_NAME } from "@/lib/auth";

type RouteContext = {
  params: Promise<{
    staffUserId: string;
  }>;
};

export async function PUT(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Sesión no encontrada" }, { status: 401 });
  }
  const { staffUserId } = await context.params;
  const payload = await request.json();
  const response = await fetch(`${BACKEND_API_BASE_URL}/staff/users/${staffUserId}/departments`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
  });
}