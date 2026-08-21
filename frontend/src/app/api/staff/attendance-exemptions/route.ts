import { NextRequest, NextResponse } from "next/server";
import { BACKEND_API_BASE_URL, SESSION_COOKIE_NAME } from "@/lib/auth";

export async function POST(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) return NextResponse.json({ detail: "Sesión no encontrada" }, { status: 401 });
  const response = await fetch(`${BACKEND_API_BASE_URL}/staff/attendance-exemptions`, { method: "POST", headers: { Authorization: `Bearer ${token}`, "content-type": "application/json" }, body: await request.text(), cache: "no-store" });
  return new NextResponse(await response.text(), { status: response.status, headers: { "content-type": response.headers.get("content-type") ?? "application/json" } });
}
