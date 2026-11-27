from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CallBriefContent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    at_a_glance: list[str]
    conversation_starters: list[str]
    what_to_verify: list[str]


class CallBrief(CallBriefContent):
    source_url: str
    source_checked_at: datetime | None
