import type { ResearchResponse, StepKey, StepStatus, StreamEvent } from "./types";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export interface StreamHandlers {
  onStep: (step: StepKey, status: StepStatus) => void;
  onResult: (data: ResearchResponse) => void;
  onError: (message: string) => void;
}

/**
 * Consume the POST /research/stream Server-Sent Events feed.
 *
 * The browser `EventSource` API only supports GET, so we POST with `fetch` and
 * read the response body as a stream, parsing `data:` frames ourselves.
 */
export async function runResearchStream(
  ticker: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/research/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
      signal,
    });
  } catch (err) {
    handlers.onError(
      `Could not reach the API at ${API_URL}. Is the FastAPI server running? (${
        err instanceof Error ? err.message : String(err)
      })`,
    );
    return;
  }

  if (!res.ok || !res.body) {
    handlers.onError(`Request failed: HTTP ${res.status}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);

      const dataLine = frame
        .split("\n")
        .find((line) => line.startsWith("data:"));
      if (!dataLine) continue;

      const payload = dataLine.slice(5).trim();
      if (!payload) continue;

      let evt: StreamEvent;
      try {
        evt = JSON.parse(payload) as StreamEvent;
      } catch {
        continue;
      }

      if (evt.type === "step") handlers.onStep(evt.step, evt.status);
      else if (evt.type === "result") handlers.onResult(evt.data);
      else if (evt.type === "error") handlers.onError(evt.message);
    }
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

export { API_URL };
