import { NextRequest, NextResponse } from "next/server";

import { BACKEND_API_BASE_URL, SESSION_COOKIE_NAME } from "@/lib/auth";

type RouteContext = {
  params: Promise<{
    path?: string[];
  }>;
};

export async function GET(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Autenticación requerida" }, { status: 401 });
  }
  const resolvedParams = await context.params;
  const segments = resolvedParams.path ?? [];
  const search = request.nextUrl.searchParams.toString();
  const upstreamPath = segments.join("/");
  const targetUrl = `${BACKEND_API_BASE_URL}/analytics${upstreamPath ? `/${upstreamPath}` : ""}${
    search ? `?${search}` : ""
  }`;

  try {
    const response = await fetch(targetUrl, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
    });
    const body = await response.text();
    const contentType = response.headers.get("content-type") ?? "application/json";
    return new NextResponse(body, {
      status: response.status,
      headers: {
        "content-type": contentType,
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Error desconocido";
    return NextResponse.json(
      { detail: "No se pudo proxy la petición", error: message },
      { status: 502 },
    );
  }
}
