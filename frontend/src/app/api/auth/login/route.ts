import { NextRequest, NextResponse } from "next/server";

import { BACKEND_API_BASE_URL, LoginResponse, SESSION_COOKIE_NAME, resolveSessionUser } from "@/lib/auth";

export async function POST(request: NextRequest) {
  try {
    const payload = await request.json();
    const response = await fetch(`${BACKEND_API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    const body = await response.text();
    const contentType = response.headers.get("content-type") ?? "application/json";

    if (!response.ok) {
      return new NextResponse(body, { status: response.status, headers: { "content-type": contentType } });
    }

    let parsed: LoginResponse;
    try {
      parsed = JSON.parse(body) as LoginResponse;
    } catch {
      return NextResponse.json(
        { detail: "El backend devolvió una respuesta de autenticación inválida." },
        { status: 502 }
      );
    }

    const nextResponse = NextResponse.json({
      ...resolveSessionUser(parsed),
      access_token: parsed.access_token,
      token_type: parsed.token_type,
    });
    nextResponse.cookies.set(SESSION_COOKIE_NAME, parsed.access_token, {
      httpOnly: true,
      sameSite: "lax",
      secure: false,
      path: "/",
      maxAge: 60 * 60 * 8,
    });
    return nextResponse;
  } catch {
    return NextResponse.json(
      { detail: "No se pudo conectar con el backend de autenticación." },
      { status: 503 }
    );
  }
}