
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Keyword


router = APIRouter(
    prefix="/keywords",
    tags=["Keywords"],
)


class KeywordCreate(BaseModel):
    phrase: str = Field(min_length=1, max_length=255)
    country_code: str = Field(
        pattern=r"^[A-Za-z]{2}$"
    )
    device: Literal["desktop", "mobile"]

    @field_validator("phrase")
    @classmethod
    def normalize_phrase(cls, value: str) -> str:
        phrase = " ".join(value.lower().split())

        if not phrase:
            raise ValueError("Keyword cannot be empty")

        return phrase

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return value.upper()


class KeywordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phrase: str
    country_code: str
    device: str


@router.post(
    "",
    response_model=KeywordResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_keyword(
    payload: KeywordCreate,
    db: Session = Depends(get_db),
):
    keyword = Keyword(
        phrase=payload.phrase,
        country_code=payload.country_code,
        device=payload.device,
    )

    db.add(keyword)

    try:
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise HTTPException(
                status_code=409,
                detail="Keyword already exists",
            ) from exc

        raise

    db.refresh(keyword)

    return keyword
