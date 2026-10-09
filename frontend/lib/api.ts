import type {
  Analysis,
  ResearchData,
  ResearchResponse,
  StepKey,
  StepStatus,
  StreamEvent,
} from "./types";

/** The API's base URL. A bare host ("api.example.com") gets https:// — without
 *  a scheme, fetch would treat it as a path on the frontend's own domain. */
function apiBase(raw: string | undefined): string {
  const value = raw?.trim().replace(/\/+$/, "");
  if (!value) return "http://localhost:8000";
  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
}

const API_URL = apiBase(process.env.NEXT_PUBLIC_API_URL);

export interface StreamHandlers {
  onStep: (step: StepKey, status: StepStatus) => void;
  /** Market data, peers and news — arrives when the Researcher finishes. */
  onData: (data: ResearchData, errors: string[]) => void;
  /** Structured analysis — arrives when the Analyst finishes. */
  onAnalysis: (analysis: Analysis | null) => void;
  /** A chunk of report markdown, as the Writer generates it. */
  onToken: (text: string) => void;
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
  options: { signal?: AbortSignal; refresh?: boolean } = {},
): Promise<void> {
  const { signal, refresh = false } = options;
  let res: Response;
  try {
    res = await fetch(`${API_URL}/research/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, refresh }),
      signal,
    });
  } catch (err) {
    if (signal?.aborted) return;
    handlers.onError(
      `Could not reach the API at ${API_URL}. Is the FastAPI server running? (${
        err instanceof Error ? err.message : String(err)
      })`,
    );
    return;
  }

  if (!res.ok || !res.body) {
    // FastAPI errors carry a human-readable `detail` (rate limit, bad ticker).
    const detail = await res
      .json()
      .then((body) => (typeof body?.detail === "string" ? body.detail : null))
      .catch(() => null);
    handlers.onError(detail ?? `Request failed: HTTP ${res.status}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;

  try {
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
        else if (evt.type === "data") handlers.onData(evt.data, evt.errors);
        else if (evt.type === "analysis") handlers.onAnalysis(evt.data);
        else if (evt.type === "token") handlers.onToken(evt.text);
        else if (evt.type === "result") {
          finished = true;
          handlers.onResult(evt.data);
        } else if (evt.type === "error") {
          finished = true;
          handlers.onError(evt.message);
        }
      }
    }
  } catch (err) {
    if (signal?.aborted) return;
    handlers.onError(
      `The connection to the API dropped mid-run (${
        err instanceof Error ? err.message : String(err)
      }).`,
    );
    return;
  }

  if (!finished && !signal?.aborted) {
    handlers.onError("The API closed the stream before the report was complete.");
  }
}

export { API_URL };
