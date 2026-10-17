// Shared types mirroring the FastAPI ResearchResponse schema.

export type StepStatus = "pending" | "running" | "done";
export type StepKey = "researcher" | "analyst" | "writer";

// Overall UI phase for a research run.
export type Phase = "idle" | "running" | "done" | "error";

export type SentimentLabel = "positive" | "neutral" | "negative" | "mixed";
export type Stance = "bullish" | "neutral" | "bearish";
export type Severity = "high" | "medium" | "low";

export interface Sentiment {
  label: SentimentLabel;
  summary: string;
  notable_headlines: string[];
}

export interface FinancialSummary {
  revenue_trend: string;
  profitability_trend: string;
  balance_sheet: string;
  commentary: string;
}

export interface Risk {
  title: string;
  detail: string;
  severity: Severity;
}

export interface Analysis {
  thesis: string;
  stance: Stance;
  stance_rationale: string;
  business_overview: string;
  bull_case: string[];
  bear_case: string[];
  catalysts: string[];
  key_risks: Risk[];
  valuation_view: string;
  recent_sentiment: Sentiment;
  financial_summary: FinancialSummary;
}

type Num = number | null;

// One income-statement period (quarter or fiscal year).
export interface StatementPeriod {
  period: string; // ISO period-end date
  revenue?: number;
  gross_profit?: number;
  operating_income?: number;
  net_income?: number;
}

export interface PricePoint {
  date: string;
  close: number;
}

// Market data from yfinance. Ratios are fractions/multiples: 0.25 = 25%,
// debt_to_equity 1.95 = 1.95x. `change_pct` alone is in percent units.
export interface Financials {
  ticker?: string;
  currency?: string | null;
  profile?: {
    name?: string | null;
    sector?: string | null;
    industry?: string | null;
    website?: string | null;
    employees?: Num;
    summary?: string | null;
  };
  price?: {
    current?: Num;
    previous_close?: Num;
    change_pct?: Num;
    fifty_two_week_high?: Num;
    fifty_two_week_low?: Num;
    beta?: Num;
  };
  valuation?: {
    market_cap?: Num;
    enterprise_value?: Num;
    trailing_pe?: Num;
    forward_pe?: Num;
    peg?: Num;
    price_to_sales?: Num;
    price_to_book?: Num;
    ev_to_ebitda?: Num;
    ev_to_revenue?: Num;
  };
  profitability?: {
    gross_margin?: Num;
    operating_margin?: Num;
    net_margin?: Num;
    return_on_equity?: Num;
    trailing_eps?: Num;
    forward_eps?: Num;
  };
  growth?: { revenue_yoy?: Num; earnings_yoy?: Num; revenue_ttm?: Num };
  balance?: {
    total_cash?: Num;
    total_debt?: Num;
    debt_to_equity?: Num;
    current_ratio?: Num;
    free_cash_flow?: Num;
    operating_cash_flow?: Num;
  };
  analyst?: {
    target_mean?: Num;
    target_high?: Num;
    target_low?: Num;
    recommendation?: string | null;
    analyst_count?: Num;
    upside_to_mean?: Num;
  };
  quarterly?: StatementPeriod[];
  annual?: StatementPeriod[];
  price_history?: PricePoint[];
}

export interface Peer {
  ticker: string;
  name: string;
  market_cap: Num;
  trailing_pe: Num;
  forward_pe: Num;
  ev_to_ebitda: Num;
  price_to_sales: Num;
  gross_margin: Num;
  operating_margin: Num;
  revenue_yoy: Num;
}

export interface NewsItem {
  title: string;
  url: string;
  source: string | null;
  published_date: string | null;
  snippet: string | null;
}

export interface Source {
  label: string;
  url: string;
  kind: "filing" | "news";
}

export interface ResearchMetadata {
  chunks_indexed?: number;
  rag_backend?: string | null;
  sec_form?: string | null;
  filing_date?: string | null;
  source_url?: string | null;
  annual_form?: string | null;
  annual_filing_date?: string | null;
  sections?: { mda: number; risk_factors: number; business: number };
  news_count?: number;
  peer_basis?: string | null;
  chat_model?: string;
  generated_at?: string; // ISO timestamp (UTC)
  cached?: boolean; // served from the API's cache rather than a fresh run
}

// What the Researcher gathers — available before the analysis and the report.
export interface ResearchData {
  ticker: string;
  company: string;
  financials: Financials;
  peers: Peer[];
  news: NewsItem[];
  sources: Source[];
  metadata: ResearchMetadata;
  /** No filings and no fundamentals were found, so no analysis is written.
   *  Absent on reports saved before the flag existed. */
  insufficient_data?: boolean;
}

export interface ResearchResponse extends ResearchData {
  report_markdown: string;
  analysis: Analysis | null;
  errors: string[];
}

// SSE event shapes emitted by POST /research/stream.
export type StreamEvent =
  | { type: "step"; step: StepKey; status: StepStatus }
  | { type: "data"; data: ResearchData; errors: string[] }
  | { type: "analysis"; data: Analysis | null }
  | { type: "token"; text: string }
  | { type: "result"; data: ResearchResponse }
  | { type: "error"; message: string };
