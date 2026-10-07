import { NextRequest, NextResponse } from "next/server";
import { BACKEND_API_BASE_URL, SESSION_COOKIE_NAME } from "@/lib/auth";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) return NextResponse.json({ detail: "Sesión no encontrada" }, { status: 401 });
  try {
    const response = await fetch(`${BACKEND_API_BASE_URL}/staff/labor-contracts?${request.nextUrl.searchParams}`, {
      headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(15000),
    });
    return new NextResponse(await response.text(), { status: response.status, headers: {
      "content-type": response.headers.get("content-type") ?? "application/json", "cache-control": "no-store",
      ...(response.headers.has("content-disposition") ? { "content-disposition": response.headers.get("content-disposition")! } : {}),
    } });
  } catch {
    return NextResponse.json({ detail: "No fue posible consultar los contratos. Intenta nuevamente." }, { status: 502 });
  }
}
