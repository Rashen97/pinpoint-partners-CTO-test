from datetime import date

from pydantic import BaseModel, ConfigDict


class ResearchFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str
    summary: str
    published_on: date
    source_url: str
    partner_evidence: str


class PartnerResearch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[ResearchFinding]
    conversation_starter: str | None
