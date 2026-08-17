import { NextRequest, NextResponse } from "next/server";

import { BACKEND_API_BASE_URL, SESSION_COOKIE_NAME } from "@/lib/auth";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Sesión no encontrada" }, { status: 401 });
  }
  const response = await fetch(`${BACKEND_API_BASE_URL}/staff/attendance-imports`, {
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
  const incomingFormData = await request.formData();
  const file = incomingFormData.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ detail: "Debes adjuntar un archivo .xlsx" }, { status: 400 });
  }

  const proxyFormData = new FormData();
  proxyFormData.append("file", file, file.name);

  const response = await fetch(`${BACKEND_API_BASE_URL}/staff/attendance-imports`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: proxyFormData,
    cache: "no-store",
  });
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
  });
}