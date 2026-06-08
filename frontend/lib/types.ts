// Shared types mirroring the FastAPI ResearchResponse schema.

export type StepStatus = "pending" | "running" | "done";
export type StepKey = "researcher" | "analyst" | "writer";

// Overall UI phase for a research run.
export type Phase = "idle" | "running" | "done" | "error";

export interface Sentiment {
  label: string;
  summary: string;
  notable_headlines: string[];
}

export interface FinancialSummary {
  pe_ratio: number | null;
  debt_to_equity: number | null;
  free_cash_flow: number | null;
  revenue_trend: string;
  net_income_trend: string;
  commentary: string;
}

export interface Analysis {
  bull_case: string[];
  bear_case: string[];
  key_risks: string[];
  recent_sentiment: Sentiment;
  financial_summary: FinancialSummary;
}

export interface ResearchMetadata {
  chunks_indexed?: number;
  sec_form?: string | null;
  filing_date?: string | null;
  source_url?: string | null;
  news_count?: number;
  chat_model?: string;
}

export interface ResearchResponse {
  ticker: string;
  company: string;
  report_markdown: string;
  analysis: Analysis | null;
  metadata: ResearchMetadata;
  errors: string[];
}

// SSE event shapes emitted by POST /research/stream.
export type StreamEvent =
  | { type: "step"; step: StepKey; status: StepStatus }
  | { type: "result"; data: ResearchResponse }
  | { type: "error"; message: string };
