"use client";

import { useCallback, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Photo, UploadInfo } from "@/lib/types";

const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 10 * 1024 * 1024;

/** Sends the file straight to storage (S3 presigned POST or the API's signed PUT) with progress. */
function send(upload: UploadInfo, file: File, onProgress: (pct: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(upload.method, upload.url);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new ApiError("Upload was rejected. Try a different photo.", xhr.status));
    xhr.onerror = () => reject(new ApiError("Upload failed. Check your connection and try again.", 0));
    if (upload.method === "POST") {
      const form = new FormData();
      Object.entries(upload.fields).forEach(([k, v]) => form.append(k, v));
      form.append("file", file); // must be last for S3
      xhr.send(form);
    } else {
      Object.entries(upload.headers).forEach(([k, v]) => xhr.setRequestHeader(k, v));
      xhr.send(file);
    }
  });
}

export function usePresignedUpload() {
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = useCallback(async (file: File): Promise<Photo | null> => {
    setError(null);
    if (!ACCEPTED.includes(file.type)) {
      setError("Use a JPEG, PNG or WebP photo.");
      return null;
    }
    if (file.size > MAX_BYTES) {
      setError("Photos must be under 10 MB.");
      return null;
    }
    setUploading(true);
    setProgress(0);
    try {
      const ticket = await api.presign({ file_name: file.name, mime_type: file.type, file_size_bytes: file.size });
      await send(ticket.upload, file, setProgress);
      return await api.confirm(ticket.asset_id);
    } catch (e) {
      setError((e as Error).message);
      return null;
    } finally {
      setUploading(false);
    }
  }, []);

  return { upload, progress, uploading, error, clearError: () => setError(null) };
}
