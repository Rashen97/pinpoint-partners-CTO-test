import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.app.db.partners import find_profile, list_directory
from backend.app.db.session import get_database
from backend.app.schemas.partners import PartnerDirectory, PartnerProfile

router = APIRouter(prefix="/partners", tags=["partners"])
Database = Annotated[sqlite3.Connection, Depends(get_database)]


@router.get("", response_model_exclude_none=True)
def list_partners(database: Database) -> PartnerDirectory:
    """List active enriched profiles with roster coverage and change history."""
    return list_directory(database)


@router.get(
    "/{partner_entry_id}",
    response_model_exclude_none=True,
    responses={404: {"description": "Enriched profile unavailable"}},
)
def get_partner_profile(partner_entry_id: str, database: Database) -> PartnerProfile:
    """Look up profile enrichment by the stable directory entry ID."""
    profile = find_profile(database, partner_entry_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Enriched profile unavailable")
    return profile
