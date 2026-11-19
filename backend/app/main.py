import logging
import sqlite3

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.routes.partners import router as partners_router

app = FastAPI(title="Pinpoint Partners API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8080", "http://localhost:8080"],
    allow_methods=["GET"],
)
app.include_router(partners_router, prefix="/api")


@app.exception_handler(sqlite3.OperationalError)
async def database_unavailable(request: Request, exc: sqlite3.OperationalError) -> JSONResponse:
    logging.getLogger(__name__).error("SQLite query failed for %s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": "Roster database unavailable"})
