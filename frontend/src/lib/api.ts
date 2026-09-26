export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Garment = {
  type: string;
  color: string;
  material: string;
  fit: string;
  details: string;
  category: "upper_body" | "lower_body" | "dresses";
};

export type OutfitSpec = {
  summary: string;
  garments: Garment[];
  accessories: string[];
  footwear: string;
  scene: string;
  style_tags: string[];
};

export type Pipeline = "edit" | "vton";

export type Generation = {
  id: string;
  image_url: string;
  source_url: string;
  spec: OutfitSpec;
  pipeline: Pipeline;
  mock: boolean;
  elapsed_ms: number;
};

export type Health = {
  status: string;
  mock: boolean;
  default_pipeline: Pipeline;
  vton_available: boolean;
  retention_days: number;
};

export type ChatMessage = { role: "user" | "assistant"; content: string };
export type OutfitSuggestion = { title: string; description: string };
export type ChatResponse = {
  reply: string;
  suggestions: OutfitSuggestion[];
  sources: string[];
  mock: boolean;
};

export type Look = {
  id: string;
  title: string;
  collection: string;
  description: string;
  image_url: string;
  spec: OutfitSpec;
  created_at: string;
};

export const mediaUrl = (path: string) => `${API_URL}${path}`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new Error(`Can't reach the LOOKBOOK API at ${API_URL}. Is the backend running?`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {}
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<Health>("/api/health"),

  generate: (opts: {
    description: string;
    photo?: File;
    sourceFile?: string;
    pipeline?: Pipeline;
  }) => {
    const form = new FormData();
    form.set("description", opts.description);
    form.set("consent", "true");
    if (opts.pipeline) form.set("pipeline", opts.pipeline);
    if (opts.photo) form.set("photo", opts.photo);
    else if (opts.sourceFile) form.set("source_file", opts.sourceFile);
    return request<Generation>("/api/generate", { method: "POST", body: form });
  },

  chat: (messages: ChatMessage[]) => request<ChatResponse>("/api/stylist/chat", json({ messages })),

  looks: (collection?: string) =>
    request<Look[]>(`/api/looks${collection ? `?collection=${encodeURIComponent(collection)}` : ""}`),

  saveLook: (generationId: string, title = "", collection = "") =>
    request<Look>("/api/looks", json({ generation_id: generationId, title, collection })),

  deleteLook: (id: string) => request<void>(`/api/looks/${id}`, { method: "DELETE" }),

  deleteAllData: () => request<void>("/api/data", { method: "DELETE" }),
};
