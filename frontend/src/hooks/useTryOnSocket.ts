"use client";

import { useEffect } from "react";
import { api, WS_URL } from "@/lib/api";
import type { Task } from "@/lib/types";
import { useTryOnStore } from "@/stores/useTryOnStore";

const MAX_RECONNECTS = 5;
const SILENCE_TIMEOUT_MS = 45_000; // server pings every 20s
const POLL_MS = 2500;

/**
 * Follows one try-on task: WebSocket first (live stage/progress events), reconnecting with
 * exponential backoff. If the socket can't be kept up, falls back to polling the REST endpoint,
 * so a flaky network or a proxy that blocks WebSockets never leaves the UI stuck.
 */
export function useTryOnSocket(taskId: string | null) {
  useEffect(() => {
    if (!taskId) return;
    const { setTask, updateStatus, setError } = useTryOnStore.getState();
    let ws: WebSocket | null = null;
    let attempts = 0;
    let done = false;
    let watchdog: ReturnType<typeof setTimeout> | undefined;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let pollTimer: ReturnType<typeof setInterval> | undefined;

    const finish = (task: Task) => {
      setTask(task);
      if (task.status === "COMPLETED" || task.status === "FAILED") {
        done = true;
        cleanup();
      }
    };

    const armWatchdog = () => {
      clearTimeout(watchdog);
      watchdog = setTimeout(() => ws?.close(), SILENCE_TIMEOUT_MS);
    };

    const startPolling = () => {
      if (pollTimer || done) return;
      pollTimer = setInterval(async () => {
        try {
          finish(await api.task(taskId));
        } catch {
          /* keep polling; transient network errors are expected here */
        }
      }, POLL_MS);
    };

    const connect = () => {
      if (done) return;
      ws = new WebSocket(`${WS_URL}/api/v1/ws/tasks/${taskId}`);
      ws.onopen = () => {
        attempts = 0;
        armWatchdog();
      };
      ws.onmessage = (event) => {
        armWatchdog();
        const msg = JSON.parse(event.data);
        if (msg.type === "snapshot") finish(msg as Task);
        else if (msg.type === "progress") updateStatus(msg.stage, msg.progress);
      };
      ws.onclose = (event) => {
        clearTimeout(watchdog);
        if (done) return;
        if (event.code === 4403) {
          setError("You don't have access to this try-on.");
          return;
        }
        if (attempts >= MAX_RECONNECTS) {
          startPolling();
          return;
        }
        const delay = Math.min(8000, 500 * 2 ** attempts++);
        retryTimer = setTimeout(connect, delay);
      };
    };

    function cleanup() {
      clearTimeout(watchdog);
      clearTimeout(retryTimer);
      clearInterval(pollTimer);
      if (ws && ws.readyState <= WebSocket.OPEN) ws.close();
    }

    connect();
    return () => {
      done = true;
      cleanup();
    };
  }, [taskId]);
}
