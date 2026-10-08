"""Pydantic schemas shared across the API and the Analyst node's structured output."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol, e.g. AAPL", min_length=1)
    refresh: bool = Field(
        False, description="Run the pipeline again even if a cached report exists."
    )


class Sentiment(BaseModel):
    """Sentiment derived from recent news coverage."""

    label: Literal["positive", "neutral", "negative", "mixed"] = Field(
        ..., description="Overall tone of recent coverage."
    )
    summary: str = Field(..., description="2-3 sentence synthesis of recent news.")
    notable_headlines: list[str] = Field(
        default_factory=list, description="Key headlines or developments driving sentiment."
    )


class FinancialSummary(BaseModel):
    """Narrative read of the fundamentals. Figures themselves are served raw
    from the market-data feed, so the model only supplies interpretation."""

    revenue_trend: str = Field(
        ..., description="Narrative on revenue across recent quarters and fiscal years."
    )
    profitability_trend: str = Field(
        ..., description="Narrative on margins and net income across recent periods."
    )
    balance_sheet: str = Field(
        ..., description="Narrative on cash, debt, leverage and cash generation."
    )
    commentary: str = Field(..., description="Overall read on financial health.")


class Risk(BaseModel):
    title: str = Field(..., description="Short name of the risk (3-8 words).")
    detail: str = Field(
        ..., description="1-2 sentences on the mechanism and what it would affect."
    )
    severity: Literal["high", "medium", "low"] = Field(
        ..., description="How material this risk is to the thesis."
    )


class Analysis(BaseModel):
    """Structured analyst output — this is the schema the LLM is constrained to."""

    thesis: str = Field(
        ..., description="2-3 sentence investment thesis summarizing the overall view."
    )
    stance: Literal["bullish", "neutral", "bearish"] = Field(
        ..., description="Overall lean implied by the evidence."
    )
    stance_rationale: str = Field(
        ..., description="One sentence on what tips the balance toward this stance."
    )
    business_overview: str = Field(
        ..., description="3-5 sentences: what the company sells, to whom, and how it makes money."
    )
    bull_case: list[str] = Field(..., description="Bullet points supporting a long thesis.")
    bear_case: list[str] = Field(..., description="Bullet points supporting a short thesis.")
    catalysts: list[str] = Field(
        default_factory=list,
        description="Upcoming events or developments that could move the stock.",
    )
    key_risks: list[Risk] = Field(..., description="Material risks to the thesis.")
    valuation_view: str = Field(
        ...,
        description=(
            "3-5 sentences on valuation: multiples versus the peer set and versus "
            "growth, and where the price sits against analyst targets."
        ),
    )
    recent_sentiment: Sentiment
    financial_summary: FinancialSummary


class NewsItem(BaseModel):
    title: str
    url: str
    source: Optional[str] = None
    published_date: Optional[str] = None
    snippet: Optional[str] = None


class Source(BaseModel):
    label: str
    url: str
    kind: Literal["filing", "news"]


class ResearchResponse(BaseModel):
    ticker: str
    company: str
    report_markdown: str
    analysis: Optional[Analysis] = None
    # Raw market data (see tools/yfinance_tool.get_financials for the shape).
    financials: dict[str, Any] = Field(default_factory=dict)
    peers: list[dict[str, Any]] = Field(default_factory=list)
    news: list[NewsItem] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
