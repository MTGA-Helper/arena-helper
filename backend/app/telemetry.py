from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from .bridge import split_telemetry_payload
from .db import get_db
from .schemas import MatchIngestRequest, MatchIngestResponse

router = APIRouter(tags=["matches"])


@router.post(
    "/matches/ingest",
    response_model=MatchIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_match(
    payload: MatchIngestRequest, db: Session = Depends(get_db)
) -> models.MatchHistory:
    if db.query(models.MatchHistory).filter_by(match_id=payload.match_id).first():
        raise HTTPException(status_code=409, detail="match_id already exists")

    normalized, raw_payload = split_telemetry_payload(payload.dict())
    history = models.MatchHistory(**normalized, raw_payload=raw_payload)
    db.add(history)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="match_id already exists")
    db.refresh(history)
    return history
