import { NextRequest, NextResponse } from "next/server";
import { BACKEND_API_BASE_URL, SESSION_COOKIE_NAME } from "@/lib/auth";
async function proxy(request: NextRequest, context: { params: Promise<{ path?: string[] }> }) {
  if (request.method !== "GET" && request.headers.get("origin") !== request.nextUrl.origin) return NextResponse.json({ detail: "Origen inválido" }, { status: 403 });
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) return NextResponse.json({ detail: "Sesión requerida" }, { status: 401 });
  const { path = [] } = await context.params;
  if (path.length > 1 || (path[0] && !/^(departments|\d+)$/.test(path[0]))) return new NextResponse(null, { status: 404 });
  try {
    const response = await fetch(`${BACKEND_API_BASE_URL}/employees/manage${path.length ? `/${path[0]}` : ""}${request.nextUrl.search}`, {
      method: request.method, headers: { Authorization: `Bearer ${token}`, "content-type": "application/json" },
      body: ["POST", "PUT"].includes(request.method) ? await request.text() : undefined,
      cache: "no-store", signal: AbortSignal.timeout(10000),
    });
    return new NextResponse(response.status === 204 ? null : await response.text(), { status: response.status, headers: { "content-type": "application/json" } });
  } catch { return NextResponse.json({ detail: "No se pudo conectar. Intenta nuevamente." }, { status: 502 }); }
}
export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;
