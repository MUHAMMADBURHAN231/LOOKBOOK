import type {
  ChatMessage,
  ChatReply,
  Garment,
  LiveToken,
  Look,
  Meta,
  Photo,
  SessionInfo,
  StylistSession,
  Task,
  UploadInfo,
  User,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const WS_URL = API_URL.replace(/^http/, "ws");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public retryAfter?: number,
  ) {
    super(message);
  }
}

// The API uses cookie sessions plus a double-submit CSRF token. We keep the token in memory
// (from GET /auth/csrf) and send it on every state-changing request.
let csrfToken: string | null = null;
let csrfPending: Promise<string> | null = null;

async function ensureCsrf(force = false): Promise<string> {
  if (csrfToken && !force) return csrfToken;
  if (!csrfPending) {
    csrfPending = fetch(`${API_URL}/api/v1/auth/csrf`, { credentials: "include" })
      .then((r) => r.json())
      .then((b) => (csrfToken = b.csrf_token as string))
      .finally(() => (csrfPending = null));
  }
  return csrfPending;
}

type Options = { method?: string; body?: unknown; signal?: AbortSignal; retried?: boolean };

export async function request<T>(path: string, opts: Options = {}): Promise<T> {
  const method = opts.method ?? "GET";
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRF-Token"] = await ensureCsrf();

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      credentials: "include",
      signal: opts.signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError("Can't reach LOOKBOOK. Check your connection and try again.", 0);
  }

  if (res.status === 403 && !opts.retried && method !== "GET") {
    const body = await res.clone().json().catch(() => ({}));
    if (String(body.detail ?? "").startsWith("Security token")) {
      await ensureCsrf(true);
      return request<T>(path, { ...opts, retried: true });
    }
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const retry = Number(res.headers.get("Retry-After")) || undefined;
    const detail = typeof body.detail === "string" ? body.detail : "Something went wrong. Please try again.";
    throw new ApiError(detail, res.status, retry);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const post = <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body ?? {} });
const del = <T>(path: string) => request<T>(path, { method: "DELETE" });

export const api = {
  meta: () => request<Meta>("/api/v1/meta"),

  // auth
  me: () => request<User>("/api/v1/auth/me"),
  signup: (b: { email: string; password: string; full_name?: string; turnstile_token?: string | null }) =>
    post<User>("/api/v1/auth/signup", b),
  login: (b: { email: string; password: string; turnstile_token?: string | null }) => post<User>("/api/v1/auth/login", b),
  logout: () => post<void>("/api/v1/auth/logout"),
  logoutAll: () => post<void>("/api/v1/auth/logout-all"),
  forgotPassword: (b: { email: string; turnstile_token?: string | null }) => post<{ detail: string }>("/api/v1/auth/password/forgot", b),
  resetPassword: (b: { token: string; new_password: string }) => post<void>("/api/v1/auth/password/reset", b),
  changePassword: (b: { current_password: string; new_password: string }) => post<void>("/api/v1/auth/password/change", b),
  sessions: () => request<SessionInfo[]>("/api/v1/auth/sessions"),
  revokeSession: (id: string) => del<void>(`/api/v1/auth/sessions/${id}`),

  // account
  setConsent: (granted: boolean) => post<void>("/api/v1/account/consent", { granted }),
  exportData: () => request<Record<string, unknown>>("/api/v1/account/export"),
  deleteData: () => del<void>("/api/v1/account/data"),
  deleteAccount: () => del<void>("/api/v1/account"),

  // media
  presign: (b: { file_name: string; mime_type: string; file_size_bytes: number }) =>
    post<{ asset_id: string; storage_key: string; upload: UploadInfo }>("/api/v1/media/presign-upload", b),
  confirm: (id: string) => post<Photo>(`/api/v1/media/${id}/confirm`),
  photos: () => request<Photo[]>("/api/v1/media/photos"),
  deletePhoto: (id: string) => del<void>(`/api/v1/media/photos/${id}`),

  // try-on
  execute: (b: {
    user_photo_id: string;
    garment_id?: string;
    prompt?: string;
    enhance_face?: boolean;
    pipeline?: "auto" | "edit" | "vton";
  }) => post<Task>("/api/v1/try-on/execute", b),
  task: (id: string) => request<Task>(`/api/v1/try-on/tasks/${id}`),
  tasks: () => request<Task[]>("/api/v1/try-on/tasks"),

  // catalog, stylist, wardrobe
  garments: (q?: string, category?: string) => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (category) p.set("category", category);
    return request<Garment[]>(`/api/v1/garments${p.size ? `?${p}` : ""}`);
  },
  chat: (message: string, session_id?: string) => post<ChatReply>("/api/v1/stylist/chat", { message, session_id }),
  stylistSessions: () => request<StylistSession[]>("/api/v1/stylist/sessions"),
  stylistMessages: (id: string) => request<ChatMessage[]>(`/api/v1/stylist/sessions/${id}`),
  deleteStylistSession: (id: string) => del<void>(`/api/v1/stylist/sessions/${id}`),
  looks: (collection?: string) =>
    request<Look[]>(`/api/v1/looks${collection ? `?collection=${encodeURIComponent(collection)}` : ""}`),
  saveLook: (b: { task_id: string; title?: string; collection?: string }) => post<Look>("/api/v1/looks", b),
  deleteLook: (id: string) => del<void>(`/api/v1/looks/${id}`),

  // live
  liveToken: () => post<LiveToken>("/api/v1/live/token"),
  widgetToken: async (key: string, host: string) => {
    const res = await fetch(`${API_URL}/api/v1/live/widget-token`, {
      method: "POST",
      headers: { "X-Lookbook-Key": key, "X-Lookbook-Host": host },
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(body.detail ?? "Live try-on is unavailable.", res.status);
    return body as LiveToken;
  },
};
