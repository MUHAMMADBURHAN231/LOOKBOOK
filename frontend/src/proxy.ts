import { type NextRequest, NextResponse } from "next/server";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// Server-side calls (inside Docker) may need a different host than the browser uses.
const API_INTERNAL_URL = (process.env.API_INTERNAL_URL ?? API_URL).replace(/\/$/, "");
// Where presigned storage URLs point (S3/R2/SeaweedFS), if not the API itself.
const STORAGE_ORIGIN = process.env.NEXT_PUBLIC_STORAGE_ORIGIN ?? "";
const SESSION_COOKIE = "lb_session";
const APP_ROUTES = ["/studio", "/live", "/stylist", "/wardrobe", "/account"];

/** Cache store-key frame policies briefly so /embed doesn't hit the API on every load. */
const framePolicyCache = new Map<string, { origins: string[]; expires: number }>();

async function frameAncestors(key: string | null): Promise<string> {
  if (!key || !/^pk_[\w-]{4,60}$/.test(key)) return "'none'";
  const cached = framePolicyCache.get(key);
  if (cached && cached.expires > Date.now()) return cached.origins.join(" ") || "'none'";
  try {
    const res = await fetch(`${API_INTERNAL_URL}/api/v1/live/frame-policy/${key}`, { cache: "no-store" });
    const origins: string[] = res.ok ? (await res.json()).allowed_origins : [];
    const safe = origins.filter((o) => /^https?:\/\/[\w.-]+(:\d+)?$/.test(o));
    framePolicyCache.set(key, { origins: safe, expires: Date.now() + 60_000 });
    return safe.join(" ") || "'none'";
  } catch {
    return "'none'";
  }
}

export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  // Signed-out visitors to app pages go to sign-in first (the API still enforces auth on every call).
  if (APP_ROUTES.some((r) => pathname === r || pathname.startsWith(`${r}/`)) && !request.cookies.has(SESSION_COOKIE)) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }

  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const isDev = process.env.NODE_ENV === "development";
  const api = new URL(API_URL);
  const apiWs = `${api.protocol === "https:" ? "wss:" : "ws:"}//${api.host}`;
  const isEmbed = pathname === "/embed";
  const ancestors = isEmbed ? await frameAncestors(request.nextUrl.searchParams.get("key")) : "'none'";

  const csp = [
    "default-src 'self'",
    // Nonce + strict-dynamic: only our own bundles (and scripts they load, e.g. Turnstile) run.
    // 'wasm-unsafe-eval' lets the 3D model's mesh decoder compile WebAssembly; it does not allow eval.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic' 'wasm-unsafe-eval'${isDev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' blob: data: ${api.origin} ${STORAGE_ORIGIN} https:`,
    "font-src 'self'",
    // API + its WebSocket, presigned storage uploads, and the realtime video service (WebRTC signalling).
    // blob: is the page's own object URLs (textures unpacked from the landing page's 3D model).
    `connect-src 'self' blob: ${api.origin} ${apiWs} ${STORAGE_ORIGIN} https: wss:`,
    "media-src 'self' blob:",
    // 'self': our own demo store frames /embed. Turnstile renders in a Cloudflare iframe.
    "frame-src 'self' https://challenges.cloudflare.com",
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    `frame-ancestors ${ancestors}`,
    ...(isDev ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("Permissions-Policy", `camera=(self), microphone=(), geolocation=()`);
  if (!isEmbed) response.headers.set("X-Frame-Options", "DENY");
  if (!isDev) response.headers.set("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload");
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!_next/static|_next/image|favicon.ico|widget.js|demo/).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
