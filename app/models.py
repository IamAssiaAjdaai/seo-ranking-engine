
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Domain(Base):
    __tablename__ = "domains"

    id: Mapped[int] = mapped_column(primary_key=True)

    hostname: Mapped[str] = mapped_column(
        String(253),
        unique=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(primary_key=True)

    phrase: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    country_code: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
    )

    device: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "phrase",
            "country_code",
            "device",
            name="uq_keyword_market_device",
        ),
        CheckConstraint(
            "device IN ('desktop', 'mobile')",
            name="ck_keyword_device",
        ),
    )


class Ranking(Base):
    __tablename__ = "rankings"

    id: Mapped[int] = mapped_column(primary_key=True)

    domain_id: Mapped[int] = mapped_column(
        ForeignKey("domains.id"),
        nullable=False,
    )

    keyword_id: Mapped[int] = mapped_column(
        ForeignKey("keywords.id"),
        nullable=False,
    )

    observed_on: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    position: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "domain_id",
            "keyword_id",
            "observed_on",
            name="uq_ranking_daily",
        ),
        CheckConstraint(
            "position BETWEEN 1 AND 100",
            name="ck_ranking_position",
        ),
        Index(
            "ix_rankings_domain_date",
            "domain_id",
            "observed_on",
        ),
    )
