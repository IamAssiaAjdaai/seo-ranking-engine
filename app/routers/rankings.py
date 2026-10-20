
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Domain, Keyword, Ranking


router = APIRouter(
    prefix="/rankings",
    tags=["Rankings"],
)


class RankingCreate(BaseModel):
    domain_id: int = Field(gt=0)
    keyword_id: int = Field(gt=0)
    observed_on: date
    position: int | None = Field(ge=1, le=100)


class RankingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    domain_id: int
    keyword_id: int
    observed_on: date
    position: int | None


@router.post(
    "",
    response_model=RankingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ranking(
    payload: RankingCreate,
    db: Session = Depends(get_db),
):
    # Check that domain exists
    domain = db.get(Domain, payload.domain_id)

    if domain is None:
        raise HTTPException(
            status_code=404,
            detail="Domain not found",
        )

    # Check that keyword exists
    keyword = db.get(Keyword, payload.keyword_id)

    if keyword is None:
        raise HTTPException(
            status_code=404,
            detail="Keyword not found",
        )

    ranking = Ranking(
        domain_id=payload.domain_id,
        keyword_id=payload.keyword_id,
        observed_on=payload.observed_on,
        position=payload.position,
    )

    db.add(ranking)

    try:
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        sqlstate = getattr(exc.orig, "sqlstate", None)

        if sqlstate == "23505":
            raise HTTPException(
                status_code=409,
                detail="Ranking already exists for this date",
            ) from exc

        if sqlstate == "23503":
            raise HTTPException(
                status_code=409,
                detail="Related domain or keyword no longer exists",
            ) from exc

        raise

    db.refresh(ranking)

    return ranking
