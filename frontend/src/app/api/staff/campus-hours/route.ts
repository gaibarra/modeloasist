import { NextRequest, NextResponse } from "next/server";
import { BACKEND_API_BASE_URL, SESSION_COOKIE_NAME } from "@/lib/auth";
import { getCurrentSessionUser } from "@/lib/server-session";
import { canViewCampusHours } from "@/lib/campus-hours";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) return NextResponse.json({ detail: "Autenticación requerida" }, { status: 401 });
  const user = await getCurrentSessionUser();
  if (!user || user.actor_type !== "staff" || !canViewCampusHours(user.email)) {
    return NextResponse.json({ detail: "Reporte restringido" }, { status: 403 });
  }
  try {
    const response = await fetch(`${BACKEND_API_BASE_URL}/staff/campus-hours?${request.nextUrl.searchParams}`, {
      headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(15000),
    });
    return new NextResponse(await response.text(), { status: response.status, headers: {
      "content-type": response.headers.get("content-type") ?? "application/json", "cache-control": "private, no-store",
      ...(response.headers.has("content-disposition") ? { "content-disposition": response.headers.get("content-disposition")! } : {}),
    } });
  } catch {
    return NextResponse.json({ detail: "No se pudo generar el reporte. Intenta nuevamente." }, { status: 502 });
  }
}
