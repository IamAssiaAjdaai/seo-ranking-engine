
import csv
import re
from datetime import date
from pathlib import Path
from typing import Iterator, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)


REQUIRED_COLUMNS = {
    "hostname",
    "phrase",
    "country_code",
    "device",
    "observed_on",
    "position",
}


HOSTNAME_PATTERN = re.compile(
    r"(?=.{1,253}$)"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
)


class RankingCSVRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str
    phrase: str = Field(min_length=1, max_length=255)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    device: Literal["desktop", "mobile"]
    observed_on: date
    position: int | None = Field(ge=1, le=100)

    @field_validator("hostname")
    @classmethod
    def normalize_hostname(cls, value: str) -> str:
        hostname = value.strip().lower().rstrip(".")

        if not HOSTNAME_PATTERN.fullmatch(hostname):
            raise ValueError("Invalid hostname")

        return hostname

    @field_validator("phrase", mode="before")
    @classmethod
    def normalize_phrase(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Missing keyword")

        phrase = " ".join(value.lower().split())

        if not phrase:
            raise ValueError("Keyword cannot be empty")

        return phrase

    @field_validator("country_code", mode="before")
    @classmethod
    def normalize_country(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Missing country code")

        return value.strip().upper()

    @field_validator("observed_on", mode="before")
    @classmethod
    def validate_date(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Missing observation date")

        date_text = value.strip()

        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_text):
            raise ValueError("Expected date YYYY-MM-DD")

        return date_text

    @field_validator("position", mode="before")
    @classmethod
    def parse_position(cls, value: object) -> int | None:
        if not isinstance(value, str):
            raise ValueError("Missing ranking position")

        position = value.strip().lower()

        if position == "unranked":
            return None

        if not re.fullmatch(r"[0-9]+", position):
            raise ValueError("Invalid ranking position")

        return int(position)


def read_ranking_csv(
    path: str | Path,
) -> Iterator[RankingCSVRow]:

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)
        headers = reader.fieldnames

        if (
            headers is None
            or len(headers) != len(REQUIRED_COLUMNS)
            or set(headers) != REQUIRED_COLUMNS
        ):
            raise ValueError("Invalid CSV columns")

        for raw_row in reader:
            try:
                yield RankingCSVRow.model_validate(raw_row)

            except ValidationError as exc:
                raise ValueError(
                    f"Invalid CSV row at line {reader.line_num}: "
                    f"{exc.errors()[0]['msg']}"
                ) from exc
