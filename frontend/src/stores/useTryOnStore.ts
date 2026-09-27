import { create } from "zustand";
import type { Garment, Photo, Task } from "@/lib/types";

export type TryOnStatus = "IDLE" | "UPLOADING" | "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface TryOnState {
  photo: Photo | null;
  garment: Garment | null;
  prompt: string;
  currentTaskId: string | null;
  status: TryOnStatus;
  stage: string;
  progress: number;
  resultImageUrl: string | null;
  task: Task | null;
  errorMessage: string | null;
  setPhoto: (p: Photo | null) => void;
  setGarment: (g: Garment | null) => void;
  setPrompt: (p: string) => void;
  setUploading: () => void;
  setTask: (task: Task) => void;
  updateStatus: (stage: string, progress: number) => void;
  setError: (msg: string) => void;
  reset: () => void;
}

const idle = {
  currentTaskId: null,
  status: "IDLE" as TryOnStatus,
  stage: "",
  progress: 0,
  resultImageUrl: null,
  task: null,
  errorMessage: null,
};

export const useTryOnStore = create<TryOnState>((set) => ({
  photo: null,
  garment: null,
  prompt: "",
  ...idle,
  setPhoto: (photo) => set({ photo }),
  setGarment: (garment) => set(garment ? { garment, prompt: "" } : { garment: null }),
  setPrompt: (prompt) => set({ prompt, garment: null }),
  setUploading: () => set({ status: "UPLOADING", errorMessage: null }),
  setTask: (task) =>
    set({
      task,
      currentTaskId: task.task_id,
      status: task.status,
      stage: task.stage,
      progress: task.progress,
      resultImageUrl: task.result_url,
      errorMessage: task.status === "FAILED" ? task.error : null,
    }),
  updateStatus: (stage, progress) =>
    set((s) =>
      s.status === "COMPLETED" || s.status === "FAILED"
        ? s
        : { stage, progress: Math.max(progress, stage === "RETRYING" ? 0 : s.progress), status: "PROCESSING" },
    ),
  setError: (errorMessage) => set({ errorMessage, status: "FAILED" }),
  reset: () => set(idle),
}));
