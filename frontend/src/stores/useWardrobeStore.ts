import { create } from "zustand";
import { api } from "@/lib/api";
import type { Look } from "@/lib/types";

interface WardrobeState {
  looks: Look[] | null;
  error: string | null;
  load: () => Promise<void>;
  save: (taskId: string, collection?: string, title?: string) => Promise<Look>;
  remove: (id: string) => Promise<void>;
}

export const useWardrobeStore = create<WardrobeState>((set, get) => ({
  looks: null,
  error: null,
  load: async () => {
    try {
      set({ looks: await api.looks(), error: null });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },
  save: async (taskId, collection, title) => {
    const look = await api.saveLook({ task_id: taskId, collection, title });
    const current = get().looks ?? [];
    set({ looks: [look, ...current.filter((l) => l.id !== look.id)] });
    return look;
  },
  remove: async (id) => {
    const previous = get().looks;
    set({ looks: (previous ?? []).filter((l) => l.id !== id) }); // optimistic
    try {
      await api.deleteLook(id);
    } catch (e) {
      set({ looks: previous, error: (e as Error).message });
    }
  },
}));
