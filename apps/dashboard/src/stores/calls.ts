import type { CallListResponse, CallSessionSummary } from "@switchboard/schemas";
import { defineStore } from "pinia";

function apiBase(): string {
  return import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
}

export const useCallsStore = defineStore("calls", {
  state: () => ({
    items: [] as CallSessionSummary[],
    loaded: false,
    error: "",
  }),
  actions: {
    async load(): Promise<void> {
      this.error = "";
      try {
        const response = await fetch(`${apiBase()}/v1/calls`);
        if (!response.ok) {
          this.error = `calls_request_failed:${response.status}`;
          this.loaded = true;
          return;
        }
        const body = (await response.json()) as CallListResponse;
        this.items = body.items;
        this.loaded = true;
      } catch {
        this.error = "calls_unreachable";
        this.loaded = true;
      }
    },
  },
});
