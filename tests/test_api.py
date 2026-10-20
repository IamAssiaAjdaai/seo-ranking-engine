
import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    "previous,current,expected_movement,expected_status",
    [
        (12, 5, 7, "improved"),
        (5, 12, -7, "declined"),
        (5, 5, 0, "unchanged"),
    ],
)
def test_ranking_comparison(
    previous,
    current,
    expected_movement,
    expected_status,
):
    response = client.post(
        "/rankings/compare",
        json={
            "previous_position": previous,
            "current_position": current,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "movement": expected_movement,
        "status": expected_status,
    }


@pytest.mark.parametrize(
    "invalid_position",
    [0, 101],
)
def test_invalid_position(invalid_position):
    response = client.post(
        "/rankings/compare",
        json={
            "previous_position": invalid_position,
            "current_position": 5,
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "previous,current",
    [
        (1, 100),
        (100, 1),
    ],
)
def test_position_boundaries(previous, current):
    response = client.post(
        "/rankings/compare",
        json={
            "previous_position": previous,
            "current_position": current,
        },
    )

    assert response.status_code == 200
    assert response.json()["movement"] == previous - current


def test_missing_required_field():
    response = client.post(
        "/rankings/compare",
        json={"previous_position": 12},
    )

    assert response.status_code == 422
