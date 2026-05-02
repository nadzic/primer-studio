from pydantic import BaseModel


class Source(BaseModel):
    title: str
    url: str
    snippet: str | None = None
    source_type: str | None = None
    reliability_score: float | None = None
    relevance_score: float | None = None
    recency_score: float | None = None
    final_source_score: float | None = None
    reason: str | None = None
