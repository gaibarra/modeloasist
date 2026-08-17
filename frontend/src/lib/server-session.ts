import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import {
  BACKEND_API_BASE_URL,
  AuthSubjectResponse,
  SESSION_COOKIE_NAME,
  SessionEmployeeUser,
  SessionStaffUser,
  SessionUser,
  SelfAttendanceRecordResponse,
  getDefaultRouteForUser,
  isAdminSessionUser,
  resolveSessionUser,
} from "@/lib/auth";
import { getSessionUserFromToken } from "@/lib/server-auth-token";

type BackendFetchInit = Omit<RequestInit, "headers"> & {
  headers?: Record<string, string>;
};

function isDynamicServerUsageError(error: unknown) {
  return (
    error instanceof Error &&
    "digest" in error &&
    error.digest === "DYNAMIC_SERVER_USAGE"
  );
}

async function getSessionToken() {
  const cookieStore = await cookies();
  return cookieStore.get(SESSION_COOKIE_NAME)?.value ?? null;
}

async function fetchBackend(path: string, init: BackendFetchInit = {}) {
  try {
    const token = await getSessionToken();
    if (!token) return null;

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);

    const response = await fetch(`${BACKEND_API_BASE_URL}${path}`, {
      ...init,
      // Attendance and schedules change during the session; never reuse a
      // server-rendered response after staff saves a new semester schedule.
      cache: init.cache ?? "no-store",
      signal: controller.signal,
      headers: {
        ...(init.headers ?? {}),
        Authorization: `Bearer ${token}`,
      },
    });

    clearTimeout(timeout);
    return response;
  } catch (error) {
    if (!isDynamicServerUsageError(error)) {
      console.error("fetchBackend error:", error);
    }
    return null;
  }
}

export async function getCurrentSessionUser(): Promise<SessionUser | null> {
  const token = await getSessionToken();
  if (!token) {
    return null;
  }

  const localUser = getSessionUserFromToken(token);
  if (localUser) {
    return localUser;
  }

  const response = await fetchBackend("/auth/me");
  if (!response || response.status === 401) {
    return null;
  }
  if (!response.ok) {
    throw new Error("No se pudo validar la sesión actual");
  }
  return resolveSessionUser((await response.json()) as AuthSubjectResponse);
}

export async function requireAuthenticatedUser() {
  const user = await getCurrentSessionUser();
  if (!user) {
    redirect("/login");
  }
  return user;
}

export async function requireResolvedUser() {
  return requireAuthenticatedUser();
}

export async function requireEmployeeUser(): Promise<SessionEmployeeUser> {
  const user = await requireAuthenticatedUser();
  if (user.actor_type !== "employee") {
    redirect(getDefaultRouteForUser(user));
  }
  return user;
}

export async function requireStaffUser(): Promise<SessionStaffUser> {
  const user = await requireAuthenticatedUser();
  if (user.actor_type !== "staff") {
    redirect(getDefaultRouteForUser(user));
  }
  return user;
}

export async function requireAdminUser() {
  const user = await requireResolvedUser();
  if (!isAdminSessionUser(user)) {
    redirect(getDefaultRouteForUser(user));
  }
  return user;
}

export async function fetchBackendJson<T>(path: string, init: BackendFetchInit = {}) {
  const response = await fetchBackend(path, init);
  if (!response || response.status === 401) {
    redirect("/login");
  }
  if (response.status === 403) {
    const user = await getCurrentSessionUser();
    redirect(user ? getDefaultRouteForUser(user) : "/login");
  }
  if (!response.ok) {
    throw new Error(`No se pudo obtener ${path}`);
  }
  return (await response.json()) as T;
}

export async function fetchOwnAttendanceRecord() {
  return fetchBackendJson<SelfAttendanceRecordResponse>("/employees/me/attendance");
}
