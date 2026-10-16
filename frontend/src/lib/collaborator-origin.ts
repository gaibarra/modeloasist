const PUBLIC_ORIGIN = "https://asistenciamodelo.online";

/** Do not derive trusted origins from client-controlled forwarded headers.
 * Next.js sees the internal listener behind Nginx, not the public HTTPS URL.
 */
export function isTrustedCollaboratorOrigin(
  origin: string | null,
  requestOrigin: string,
  development = process.env.NODE_ENV === "development",
): boolean {
  if (origin === PUBLIC_ORIGIN) return true;
  if (!development || !origin || origin !== requestOrigin) return false;
  try {
    const url = new URL(origin);
    return url.origin === origin && ["http:", "https:"].includes(url.protocol) &&
      ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  } catch {
    return false;
  }
}
