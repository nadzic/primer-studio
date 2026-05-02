from pydantic import BaseModel


class EvidenceItem(BaseModel):
    claim: str
    category: str
    source_url: str
    source_type: str
    period: str | None = None
    metric: str | None = None
    value: str | None = None
    comparison_type: str | None = None

    evidence_strength: str | None = None
    fact_or_interpretation: str | None = None
    confidence: float | None = None
    reason: str | None = None

    inclusion_score: float | None = None
    used_for: list[str] | None = None
