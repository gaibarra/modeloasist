import "server-only";

import { createHmac, timingSafeEqual } from "node:crypto";

import { AuthSubjectResponse, SessionUser, resolveSessionUser } from "@/lib/auth";

type TokenPayload = {
  exp?: number;
  session?: AuthSubjectResponse;
};

function b64urlDecode(value: string) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padding = "=".repeat((4 - (normalized.length % 4)) % 4);
  return Buffer.from(`${normalized}${padding}`, "base64");
}

function getSessionSecret() {
  return process.env.AUTH_SECRET_KEY?.trim() || null;
}

function verifySignature(token: string, secret: string) {
  const [encodedHeader, encodedPayload, encodedSignature] = token.split(".", 3);
  if (!encodedHeader || !encodedPayload || !encodedSignature) {
    return false;
  }

  const message = `${encodedHeader}.${encodedPayload}`;
  const expected = createHmac("sha256", secret).update(message).digest();
  const received = b64urlDecode(encodedSignature);

  return received.length === expected.length && timingSafeEqual(received, expected);
}

function decodePayload(token: string): TokenPayload | null {
  const parts = token.split(".", 3);
  if (parts.length !== 3) {
    return null;
  }

  try {
    return JSON.parse(b64urlDecode(parts[1]).toString("utf-8")) as TokenPayload;
  } catch {
    return null;
  }
}

export function getSessionUserFromToken(token: string): SessionUser | null {
  const secret = getSessionSecret();
  if (!secret || !verifySignature(token, secret)) {
    return null;
  }

  const payload = decodePayload(token);
  if (!payload || typeof payload.exp !== "number" || Date.now() >= payload.exp * 1000) {
    return null;
  }

  const subject = payload.session;
  if (!subject || (subject.actor_type !== "employee" && subject.actor_type !== "staff")) {
    return null;
  }

  return resolveSessionUser(subject);
}