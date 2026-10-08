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

- **Researcher** — pulls three sections from SEC EDGAR: the **MD&A** from the
  latest periodic report (10-K / 10-Q), and **Risk Factors** (Item 1A) and
  **Business** (Item 1) from the latest annual report (20-F for foreign
  issuers). From **yfinance** it takes a year of prices, valuation multiples,
  margins, growth, balance-sheet and cash-flow figures, analyst targets,
  quarterly and annual income statements, and a peer set. Recent news comes
  from **Tavily**. The filing sections are indexed into Qdrant.
- **Analyst** — synthesizes a structured `Analysis` JSON (`thesis`, `stance`,
  `bull_case`, `bear_case`, `catalysts`, `key_risks`, `valuation_view`,
  `recent_sentiment`, `financial_summary`), querying the **Qdrant
  `sec_filings`** collection section by section for specific clauses.
- **Writer** — renders a markdown note from the analysis and the raw figures:
  Executive Summary, Business Overview, Financial Highlights, Valuation & Peers,
  Bull Case vs. Bear Case, Risk Factors, Recent News & Sentiment, Conclusion.

## Project layout

```
backend/
  config.py            # env-driven settings
  llm.py               # ChatOpenAI factory
  models.py            # Pydantic schemas (API + Analysis structured output)
  main.py              # FastAPI app — POST /research
  tools/
    sec_edgar.py       # EDGAR filings + Item section extraction
    yfinance_tool.py   # market data, fundamentals, peers
    tavily_news.py     # recent news
  rag/
    chunking.py        # tiktoken 500/50 chunking
    embeddings.py      # text-embedding-3-small
    qdrant_store.py    # sec_filings collection: index + query
  guard.py             # rate limiter + TTL response cache
  graph/
    state.py           # shared graph state
    formatting.py      # data sheets shared by the Analyst and Writer prompts
    pipeline.py        # LangGraph assembly + run_research()
    nodes/
      researcher.py
      analyst.py
      writer.py
frontend/              # Next.js (App Router) + Tailwind UI
  app/
    page.tsx           # run state, SSE wiring, tabs
    layout.tsx
    globals.css        # Tailwind + design tokens (light/dark) + report typography
  components/
    TopBar.tsx         # ticker input, run/stop, saved-report history
    Pipeline.tsx       # live Researcher/Analyst/Writer status
    Dashboard.tsx      # overview: hero, KPIs, charts, thesis, peers, news
    Hero.tsx  KpiGrid.tsx  Thesis.tsx  PeersTable.tsx  NewsList.tsx
    charts/            # SVG price, revenue/net-income and target-range charts
    ReportView.tsx     # react-markdown report + copy / download / print
    RunDetails.tsx     # sources, filing coverage, pipeline warnings
  lib/
    api.ts             # SSE-over-fetch client
    format.ts          # number/date formatting
    history.ts         # finished reports kept in localStorage
    types.ts
scripts/
  research_cli.py      # run the pipeline from the terminal
tests/                 # pytest suite (no network or API keys needed)
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
python -m uvicorn backend.main:app --reload --port 8000
# POST /research  body: {"ticker": "AAPL"}  (add "refresh": true to bypass the cache)
# docs at http://localhost:8000/docs
```

**UI** (terminal 2) — Next.js:

```bash
cd frontend
npm install        # first time only
npm run dev        # http://localhost:3000
```

The UI consumes the API's streaming endpoint (`POST /research/stream`): the
dashboard fills in with market data as soon as the Researcher finishes, then the
analysis, then the report as it is written. If the API isn't on `http://localhost:8000`, set
`NEXT_PUBLIC_API_URL` in `frontend/.env.local` (see `.env.local.example`).

**Or skip the servers** and run the pipeline directly:

```bash
python -m scripts.research_cli AAPL
```

A `Makefile` wraps these: `make install`, `make api`, `make ui-install` (once),
`make ui`, `make cli TICKER=MSFT`.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

The suite fakes the pipeline, yfinance and the clock, so it needs no network
access or API keys. It covers filing-section extraction, market-data
normalization, prompt data sheets, the rate limiter and cache, and the API's
streaming, caching and rate-limiting behaviour.

## Deploying publicly

Every uncached run spends LLM, embedding and search credits, so the API ships
with limits (all env vars, see `.env.example`):

| Variable              | Default | Effect                                              |
|-----------------------|---------|-----------------------------------------------------|
| `RATE_LIMIT_PER_HOUR` | `10`    | New runs per client IP per hour                     |
| `RATE_LIMIT_PER_DAY`  | `200`   | New runs in total per day — the hard cap on spend   |
| `CACHE_TTL_MINUTES`   | `60`    | A finished report is reused for this long, for free |
| `ALLOWED_ORIGINS`     | `*`     | Set to the frontend's URL so other sites can't call the API from a browser |
| `ALLOWED_ORIGIN_REGEX`| unset   | Extra origins by pattern, e.g. Vercel preview deployments |

Limits and cache live in process memory: they reset on restart and aren't
shared between instances, which is fine for a single Railway service.

## Design notes

- **Live progress via SSE.** `POST /research/stream` streams real LangGraph
  events: `step` (a node started/finished), `data` (market data, peers, news and
  sources once the Researcher is done), `analysis`, `token` (report markdown as
  the Writer generates it) and the final `result`. `POST /research` remains for
  a single blocking JSON response.
- **Figures come from the data, not the model.** The response carries the raw
  `financials`, `peers` and `news`; the dashboard renders those directly and the
  Writer is given the same data sheet, so the LLM only supplies interpretation.
- **Retrieval works without a Qdrant server.** If `QDRANT_URL` can't be reached
  (no local container, a suspended cloud cluster), an in-process Qdrant store
  is used for the run instead.
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
