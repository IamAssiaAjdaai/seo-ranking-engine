
from datetime import date
from pathlib import Path

import pytest

from app.services.csv_parser import read_ranking_csv


HEADER = (
    "hostname,phrase,country_code,"
    "device,observed_on,position\n"
)


def write_csv(
    tmp_path: Path,
    row: str,
    header: str = HEADER,
) -> Path:
    path = tmp_path / "test_rankings.csv"
    path.write_text(
        header + row + "\n",
        encoding="utf-8",
    )
    return path


def test_valid_row_and_normalization(tmp_path):
    path = write_csv(
        tmp_path,
        " EXAMPLE.DE. ,  SEO   Agentur   Bonn  ,"
        "de,desktop,2026-10-20,12",
    )

    rows = list(read_ranking_csv(path))

    assert len(rows) == 1
    assert rows[0].hostname == "example.de"
    assert rows[0].phrase == "seo agentur bonn"
    assert rows[0].country_code == "DE"
    assert rows[0].position == 12
    assert rows[0].observed_on == date(2026, 10, 20)


def test_unranked_position(tmp_path):
    path = write_csv(
        tmp_path,
        "example.de,seo software,DE,"
        "mobile,2026-10-20,unranked",
    )

    rows = list(read_ranking_csv(path))

    assert rows[0].position is None


@pytest.mark.parametrize(
    "position",
    ["0", "101", "abc", ""],
)
def test_invalid_position(tmp_path, position):
    path = write_csv(
        tmp_path,
        "example.de,seo software,DE,"
        f"desktop,2026-10-20,{position}",
    )

    with pytest.raises(
        ValueError,
        match="Invalid CSV row at line 2",
    ):
        list(read_ranking_csv(path))


def test_missing_position(tmp_path):
    path = write_csv(
        tmp_path,
        "example.de,seo software,DE,"
        "desktop,2026-10-20",
    )

    with pytest.raises(ValueError):
        list(read_ranking_csv(path))


def test_missing_country(tmp_path):
    path = write_csv(
        tmp_path,
        "example.de,seo software",
    )

    with pytest.raises(ValueError):
        list(read_ranking_csv(path))


def test_invalid_date(tmp_path):
    path = write_csv(
        tmp_path,
        "example.de,seo software,DE,"
        "desktop,2026-02-30,12",
    )

    with pytest.raises(ValueError):
        list(read_ranking_csv(path))


def test_invalid_device(tmp_path):
    path = write_csv(
        tmp_path,
        "example.de,seo software,DE,"
        "tablet,2026-10-20,12",
    )

    with pytest.raises(ValueError):
        list(read_ranking_csv(path))


def test_missing_csv_column(tmp_path):
    path = write_csv(
        tmp_path,
        "example.de,seo software,DE,"
        "desktop,2026-10-20",
        header=(
            "hostname,phrase,country_code,"
            "device,observed_on\n"
        ),
    )

    with pytest.raises(
        ValueError,
        match="Invalid CSV columns",
    ):
        list(read_ranking_csv(path))
