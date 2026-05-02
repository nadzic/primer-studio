from typing import Literal

from pydantic import BaseModel, Field


class SignalRequest(BaseModel):
    query: str = Field(..., min_length=15, description="User request")
    symbol: str | None = Field(None, description="Ticker symbol, e.g. AAPL")
    horizon: Literal["intraday", "swing", "position"] | None = None


class SignalResponse(BaseModel):
    symbol: str
    signal: str
    confidence: float = Field(..., ge=0, le=1)
    reasoning: str
    warning: str | None = None
    error: str | None = None
