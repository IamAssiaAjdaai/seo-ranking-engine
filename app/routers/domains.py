
import re
from datetime import datetime

from fastapi import Query, Path
from sqlalchemy import select

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Domain


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
