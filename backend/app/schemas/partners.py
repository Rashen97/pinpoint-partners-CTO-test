from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class PartnerEntry(BaseModel):
    partner_entry_id: str
    firm_key: str
    firm_name: str
    name: str
    role: str
    offices: list[str] = Field(default_factory=list)
    practices: list[str] = Field(default_factory=list)
    profile_url: str


class RosterCoverage(BaseModel):
    verified_firm_count: int
    target_firm_count: int


class RosterChange(BaseModel):
    name: str
    firm_name: str
    kind: Literal["newly_listed", "no_longer_listed"]
    observed_at: date | datetime
    source_url: str | None = None


class PartnerDirectory(BaseModel):
    records: list[PartnerEntry]
    coverage: RosterCoverage | None = None
    changes: list[RosterChange] | None = None


class PartnerProfile(BaseModel):
    biography: str | None = None
    email: str | None = None
    phone_numbers: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    admissions: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    source_checked_at: datetime | None = None
