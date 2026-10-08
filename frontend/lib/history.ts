import type { ResearchResponse } from "./types";

// Finished reports are kept in this browser so a refresh doesn't lose them.
const KEY = "equity-research:history:v1";
const MAX_ENTRIES = 8;

export interface HistoryEntry {
  savedAt: string; // ISO timestamp
  report: ResearchResponse;
}

export function loadHistory(): HistoryEntry[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

/** Put `report` first, replacing any earlier run of the same ticker. */
export function saveToHistory(report: ResearchResponse): HistoryEntry[] {
  const entries = [
    { savedAt: new Date().toISOString(), report },
    ...loadHistory().filter((e) => e.report.ticker !== report.ticker),
  ].slice(0, MAX_ENTRIES);
  // Storage can be full or blocked; drop the oldest entries until it fits.
  for (let n = entries.length; n > 0; n--) {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(entries.slice(0, n)));
      return entries.slice(0, n);
    } catch {
      continue;
    }
  }
  return entries;
}

export function clearHistory(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    // Nothing stored, nothing to clear.
  }
}
