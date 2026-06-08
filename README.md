# Equity Research Agent

A LangGraph multi-agent pipeline that produces an equity research report from a
single ticker. Three nodes run in sequence:

```
            ┌────────────┐     ┌──────────┐     ┌────────┐
  ticker ─▶ │ Researcher │ ──▶ │ Analyst  │ ──▶ │ Writer │ ──▶ markdown report
            └────────────┘     └──────────┘     └────────┘
              SEC EDGAR          structured        polished
              yfinance           JSON analysis     markdown
              Tavily news        (+ Qdrant RAG)
```

- **Researcher** — pulls the latest 10-K/10-Q **MD&A** from SEC EDGAR (the
  `data.sec.gov` submissions API resolves the exact primary document, with the
  `efts.sec.gov` full-text search API as a fallback), fundamentals from
  **yfinance** (P/E, last 4 quarters of revenue & net income, debt-to-equity,
  free cash flow), and recent news from **Tavily**. It indexes the MD&A into Qdrant.
- **Analyst** — synthesizes a structured `Analysis` JSON (`bull_case`,
  `bear_case`, `key_risks`, `recent_sentiment`, `financial_summary`), querying
  the **Qdrant `sec_filings`** collection for specific MD&A clauses.
- **Writer** — renders a clean markdown report: Executive Summary, Financial
  Highlights, Risk Factors, Recent News & Sentiment, Conclusion.

## Project layout

```
backend/
  config.py            # env-driven settings
  llm.py               # ChatOpenAI factory
  models.py            # Pydantic schemas (API + Analysis structured output)
  main.py              # FastAPI app — POST /research
  tools/
    sec_edgar.py       # EDGAR full-text search + MD&A extraction
    yfinance_tool.py   # fundamentals
    tavily_news.py     # recent news
  rag/
    chunking.py        # tiktoken 500/50 chunking
    embeddings.py      # text-embedding-3-small
    qdrant_store.py    # sec_filings collection: index + query
  graph/
    state.py           # shared graph state
    pipeline.py        # LangGraph assembly + run_research()
    nodes/
      researcher.py
      analyst.py
      writer.py
frontend/              # Next.js (App Router) + Tailwind UI
  app/
    page.tsx           # two-column layout, state + SSE wiring
    layout.tsx
    globals.css        # Tailwind + dark theme + report typography
  components/
    Sidebar.tsx        # ticker input + run details
    ProgressTracker.tsx# live Researcher/Analyst/Writer status
    ReportView.tsx     # react-markdown + remark-gfm
    SkeletonLoader.tsx
  lib/
    api.ts             # SSE-over-fetch client
    types.ts
scripts/
  research_cli.py      # run the pipeline from the terminal
```

## Setup

1. **Install dependencies** (Python 3.10+):

   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure secrets** — copy the template and fill in your keys:

   ```bash
   cp .env.example .env
   ```

   | Variable          | Purpose                                             |
   |-------------------|-----------------------------------------------------|
   | `OPENAI_API_KEY`  | LLM (Analyst/Writer) **and** embeddings             |
   | `TAVILY_API_KEY`  | Recent news search                                  |
   | `QDRANT_URL`      | Qdrant endpoint (Cloud URL or `http://localhost:6333`) |
   | `QDRANT_API_KEY`  | Qdrant Cloud key (blank for local docker)           |
   | `SEC_USER_AGENT`  | Required by SEC — set to `name email@example.com`   |

   A local Qdrant is one command:

   ```bash
   docker run -p 6333:6333 qdrant/qdrant
   ```

## Run

**API** (terminal 1):

```bash
uvicorn backend.main:app --reload --port 8000
# POST /research  body: {"ticker": "AAPL"}
# docs at http://localhost:8000/docs
```

**UI** (terminal 2) — Next.js:

```bash
cd frontend
npm install        # first time only
npm run dev        # http://localhost:3000
```

The UI consumes the API's streaming endpoint (`POST /research/stream`) to show
live per-agent progress. If the API isn't on `http://localhost:8000`, set
`NEXT_PUBLIC_API_URL` in `frontend/.env.local` (see `.env.local.example`).

**Or skip the servers** and run the pipeline directly:

```bash
python -m scripts.research_cli AAPL
```

A `Makefile` wraps these: `make install`, `make api`, `make ui-install` (once),
`make ui`, `make cli TICKER=MSFT`.

## Design notes

- **Live progress via SSE.** `POST /research/stream` streams real LangGraph
  node-completion events (`researcher`/`analyst`/`writer` → running/done), so the
  UI tracker reflects the actual pipeline rather than a timer. `POST /research`
  remains for a single blocking JSON response.
- **Graceful degradation.** Every external call (SEC, yfinance, Tavily, Qdrant,
  OpenAI) is wrapped so a single failure doesn't sink the run — the pipeline
  returns a report plus a list of non-fatal `errors`. The Analyst and Writer
  have deterministic fallbacks if the LLM is unavailable.
- **Models are swappable.** `CHAT_MODEL` and `EMBEDDING_MODEL` are env vars; the
  chat nodes go through `backend/llm.py`, so pointing at a different OpenAI model
  (or compatible endpoint) is a one-line change. The embedding dimension
  (`EMBEDDING_DIM`, 1536 for `text-embedding-3-small`) must match the Qdrant
  collection.
- **SEC etiquette.** Requests are lightly rate-limited and send a `User-Agent`
  in SEC's required `Name email@domain` format — parenthetical or browser-like
  User-Agents are rejected with HTTP 403, so set `SEC_USER_AGENT` to your own
  name + email in `.env`.

> ⚠️ Generated reports are for informational purposes only and are **not
> investment advice**.
