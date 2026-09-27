/** Only allow same-site relative paths after sign-in (blocks open redirects like //evil.com). */
export function safeNext(value: string | null | undefined, fallback = "/studio"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return fallback;
  return value;
}
