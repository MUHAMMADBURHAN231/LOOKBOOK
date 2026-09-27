export type User = {
  id: string;
  email: string;
  full_name: string | null;
  biometric_consent_granted: boolean;
  created_at: string;
};

export type SessionInfo = {
  id: string;
  created_at: string;
  last_seen_at: string;
  user_agent: string | null;
  current: boolean;
};

export type UploadInfo = {
  url: string;
  method: "POST" | "PUT";
  fields: Record<string, string>;
  headers: Record<string, string>;
  expires_in: number;
};

export type Photo = {
  id: string;
  url: string;
  width: number | null;
  height: number | null;
  is_primary: boolean;
  created_at: string;
};

export type Garment = {
  id: string;
  slug: string;
  title: string;
  category: string;
  brand: string | null;
  color: string | null;
  season: string | null;
  description: string;
  price_cents: number | null;
  image_url: string;
  similarity: number | null;
};

export type GarmentSpec = {
  type: string;
  color: string;
  material: string;
  fit: string;
  details: string;
  category: string;
};

export type OutfitSpec = {
  summary: string;
  garments: GarmentSpec[];
  accessories: string[];
  footwear: string;
  scene: string;
  style_tags: string[];
};

export type TaskStatus = "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";

export type Task = {
  task_id: string;
  status: TaskStatus;
  stage: string;
  progress: number;
  result_url: string | null;
  error: string | null;
  garment_id: string | null;
  prompt: string | null;
  outfit_spec: OutfitSpec | null;
  adapter: string | null;
  execution_time_ms: number | null;
  created_at: string;
};

export type Look = {
  id: string;
  task_id: string;
  title: string;
  collection: string;
  image_url: string | null;
  prompt: string | null;
  garment_id: string | null;
  created_at: string;
};

export type ChatReply = {
  session_id: string;
  reply: string;
  recommended_garments: Garment[];
  tools_used: string[];
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  garments: Garment[];
  created_at: string;
};

export type StylistSession = { id: string; title: string; updated_at: string };

export type Meta = {
  mock: boolean;
  tryon_adapter: string;
  edit_available: boolean;
  live_available: boolean;
  embedding_model: string;
  raw_upload_retention_days: number;
  max_upload_bytes: number;
};

export type LiveToken = { mock: boolean; api_key: string | null; expires_at: string | null; model: string };
