
import re
from datetime import date, datetime

from app.models import Domain, Ranking, Keyword
from fastapi import Query, Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from typing import Literal

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, aliased

from app.services.ranking_changes import compare_positions
from app.database import get_db


router = APIRouter(
    prefix="/domains",
    tags=["Domains"],
)

HOSTNAME_PATTERN = re.compile(
    r"^(?=.{1,253}$)"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


class DomainCreate(BaseModel):
    hostname: str

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, value: str) -> str:
        hostname = value.strip().lower().rstrip(".")

        if not HOSTNAME_PATTERN.fullmatch(hostname):
            raise ValueError(
                "Provide a hostname such as example.de"
            )

        return hostname


class DomainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hostname: str
    created_at: datetime

class RankingHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    keyword_id: int
    observed_on: date
    position: int | None

class RankingChangeResponse(BaseModel):
    keyword_id: int
    phrase: str
    country_code: str
    device: str

    previous_position: int | None
    current_position: int | None

    movement: int | None

    status: Literal[
        "improved",
        "declined",
        "unchanged",
        "new",
        "lost",
        "unranked",
    ]

@router.post(
    "",
    response_model=DomainResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_domain(
    payload: DomainCreate,
    db: Session = Depends(get_db),
):
    domain = Domain(hostname=payload.hostname)

    db.add(domain)

    try:
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise HTTPException(
                status_code=409,
                detail="Domain already exists",
            ) from exc

        raise

    db.refresh(domain)

    return domain

@router.get("", response_model=list[DomainResponse])
def list_domains(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    statement = (
        select(Domain)
        .order_by(Domain.id)
        .offset(offset)
        .limit(limit)
    )

    return db.scalars(statement).all()


@router.get("/{domain_id}", response_model=DomainResponse)
def get_domain(
    domain_id: int = Path(ge=1),
    db: Session = Depends(get_db),
):
    domain = db.get(Domain, domain_id)

    if domain is None:
        raise HTTPException(
            status_code=404,
            detail="Domain not found",
        )

    return domain

@router.get(
    "/{domain_id}/rankings",
    response_model=list[RankingHistoryItem],
)
def get_domain_rankings(
    domain_id: int = Path(ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    domain = db.get(Domain, domain_id)

    if domain is None:
        raise HTTPException(
            status_code=404,
            detail="Domain not found",
        )

    statement = (
        select(Ranking)
        .where(Ranking.domain_id == domain_id)
        .order_by(
            Ranking.observed_on.desc(),
            Ranking.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    rankings = db.scalars(statement).all()

    return rankings

@router.get(
    "/{domain_id}/changes",
    response_model=list[RankingChangeResponse],
)
def get_ranking_changes(
    domain_id: int = Path(ge=1),
    from_date: date = Query(...),
    to_date: date = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    if to_date <= from_date:
        raise HTTPException(
            status_code=422,
            detail="to_date must be after from_date",
        )

    if db.get(Domain, domain_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Domain not found",
        )

    previous = aliased(Ranking)
    current = aliased(Ranking)

    statement = (
        select(
            Keyword.id,
            Keyword.phrase,
            Keyword.country_code,
            Keyword.device,
            previous.position,
            current.position,
        )
        .join(
            previous,
            previous.keyword_id == Keyword.id,
        )
        .join(
            current,
            and_(
                current.domain_id == previous.domain_id,
                current.keyword_id == previous.keyword_id,
                current.observed_on == to_date,
            ),
        )
        .where(
            previous.domain_id == domain_id,
            previous.observed_on == from_date,
        )
        .order_by(Keyword.id)
        .limit(limit)
        .offset(offset)
    )

    rows = db.execute(statement).all()

    results = []

    for (
        keyword_id,
        phrase,
        country_code,
        device,
        previous_position,
        current_position,
    ) in rows:

        movement, ranking_status = compare_positions(
            previous_position,
            current_position,
        )

        results.append(
            RankingChangeResponse(
                keyword_id=keyword_id,
                phrase=phrase,
                country_code=country_code,
                device=device,
                previous_position=previous_position,
                current_position=current_position,
                movement=movement,
                status=ranking_status,
            )
        )

    return results
