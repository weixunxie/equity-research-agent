"""Pydantic schemas shared across the API and the Analyst node's structured output."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol, e.g. AAPL", min_length=1)


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
    """Narrative + key figures distilled from the fundamentals."""

    pe_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    free_cash_flow: Optional[float] = None
    revenue_trend: str = Field(
        ..., description="Narrative on the last 4 quarters of revenue."
    )
    net_income_trend: str = Field(
        ..., description="Narrative on the last 4 quarters of net income."
    )
    commentary: str = Field(..., description="Overall read on financial health.")


class Analysis(BaseModel):
    """Structured analyst output — this is the schema the LLM is constrained to."""

    bull_case: list[str] = Field(..., description="Bullet points supporting a long thesis.")
    bear_case: list[str] = Field(..., description="Bullet points supporting a short thesis.")
    key_risks: list[str] = Field(..., description="Material risks to the thesis.")
    recent_sentiment: Sentiment
    financial_summary: FinancialSummary


class ResearchResponse(BaseModel):
    ticker: str
    company: str
    report_markdown: str
    analysis: Optional[Analysis] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
