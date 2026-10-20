
import os
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Domain, Keyword, Ranking

from sqlalchemy.exc import IntegrityError

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app

@pytest.fixture
def db_connection():
    # Never run database tests against development DB
    if os.environ.get("POSTGRES_DB") != "seo_rankings_test":
        pytest.skip("Test database is not selected")

    from app.database import engine

    with engine.connect() as connection:
        transaction = connection.begin()

        try:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

            if database_name != "seo_rankings_test":
                pytest.fail("Unsafe database connection")

            yield connection

        finally:
            transaction.rollback()

def test_insert_and_read_ranking(db_connection):
    unique_id = uuid4().hex[:12]

    # Insert data
    with Session(
        bind=db_connection,
        join_transaction_mode="create_savepoint",
    ) as session:
        domain = Domain(
            hostname=f"test-{unique_id}.example"
        )

        keyword = Keyword(
            phrase=f"seo test {unique_id}",
            country_code="DE",
            device="desktop",
        )

        session.add_all([domain, keyword])
        session.flush()

        ranking = Ranking(
            domain_id=domain.id,
            keyword_id=keyword.id,
            observed_on=date(2026, 10, 20),
            position=5,
        )

        session.add(ranking)
        session.flush()

        ranking_id = ranking.id
        session.commit()

    # Read data in a new session
    with Session(
        bind=db_connection,
        join_transaction_mode="create_savepoint",
    ) as session:
        saved_ranking = session.scalar(
            select(Ranking).where(
                Ranking.id == ranking_id
            )
        )

        assert saved_ranking is not None
        assert saved_ranking.position == 5

def create_test_entities(session: Session):
    unique_id = uuid4().hex[:12]

    domain = Domain(
        hostname=f"constraint-{unique_id}.example"
    )

    keyword = Keyword(
        phrase=f"seo constraint {unique_id}",
        country_code="DE",
        device="desktop",
    )

    session.add_all([domain, keyword])
    session.flush()

    return domain.id, keyword.id

def test_duplicate_ranking_rejected(db_connection):
    with Session(
        bind=db_connection,
        join_transaction_mode="create_savepoint",
    ) as session:

        domain_id, keyword_id = create_test_entities(
            session
        )

        first_ranking = Ranking(
            domain_id=domain_id,
            keyword_id=keyword_id,
            observed_on=date(2026, 10, 20),
            position=5,
        )

        session.add(first_ranking)
        session.flush()

        duplicate = Ranking(
            domain_id=domain_id,
            keyword_id=keyword_id,
            observed_on=date(2026, 10, 20),
            position=8,
        )

        session.add(duplicate)

        with pytest.raises(IntegrityError) as exc:
            session.flush()

        assert exc.value.orig.sqlstate == "23505"

        session.rollback()

def test_invalid_position_rejected(db_connection):
    with Session(
        bind=db_connection,
        join_transaction_mode="create_savepoint",
    ) as session:

        domain_id, keyword_id = create_test_entities(
            session
        )

        ranking = Ranking(
            domain_id=domain_id,
            keyword_id=keyword_id,
            observed_on=date(2026, 10, 20),
            position=101,
        )

        session.add(ranking)

        with pytest.raises(IntegrityError) as exc:
            session.flush()

        assert exc.value.orig.sqlstate == "23514"

        session.rollback()

def test_invalid_foreign_key_rejected(db_connection):
    with Session(
        bind=db_connection,
        join_transaction_mode="create_savepoint",
    ) as session:

        _, keyword_id = create_test_entities(
            session
        )

        ranking = Ranking(
            domain_id=-1,
            keyword_id=keyword_id,
            observed_on=date(2026, 10, 20),
            position=5,
        )

        session.add(ranking)

        with pytest.raises(IntegrityError) as exc:
            session.flush()

        assert exc.value.orig.sqlstate == "23503"

        session.rollback()

def test_create_domain_api(db_connection):

    def override_get_db():
        with Session(
            bind=db_connection,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        hostname = f"api-{uuid4().hex[:12]}.example"

        with TestClient(app) as client:

            # New domain
            response = client.post(
                "/domains",
                json={"hostname": f"  {hostname.upper()}  "},
            )

            assert response.status_code == 201
            assert response.json()["hostname"] == hostname
            assert isinstance(response.json()["id"], int)

            # Duplicate domain
            duplicate = client.post(
                "/domains",
                json={"hostname": hostname},
            )

            assert duplicate.status_code == 409

            # Invalid hostname
            invalid = client.post(
                "/domains",
                json={"hostname": "https://example.de/path"},
            )

            assert invalid.status_code == 422

    finally:
        app.dependency_overrides.pop(get_db, None)

def test_domain_read_endpoints(db_connection):

    def override_get_db():
        with Session(
            bind=db_connection,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        hostname = f"read-{uuid4().hex[:12]}.example"

        with TestClient(app) as client:
            created = client.post(
                "/domains",
                json={"hostname": hostname},
            )

            assert created.status_code == 201
            domain_id = created.json()["id"]

            # Read specific domain
            detail = client.get(f"/domains/{domain_id}")

            assert detail.status_code == 200
            assert detail.json()["hostname"] == hostname

            # List domains
            listing = client.get(
                "/domains",
                params={"limit": 100, "offset": 0},
            )

            assert listing.status_code == 200
            assert any(
                item["id"] == domain_id
                for item in listing.json()
            )

            # Pagination
            page = client.get(
                "/domains",
                params={"limit": 1, "offset": 0},
            )

            assert page.status_code == 200
            assert len(page.json()) == 1

            # Invalid pagination
            invalid = client.get(
                "/domains",
                params={"limit": 0},
            )
            assert invalid.status_code == 422

            # Missing domain
            missing = client.get(
                "/domains/999999999"
            )
            assert missing.status_code == 404

    finally:
        app.dependency_overrides.pop(get_db, None)

def test_create_keyword_api(db_connection):

    def override_get_db():
        with Session(
            bind=db_connection,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        phrase = f"seo backend {uuid4().hex[:12]}"

        with TestClient(app) as client:

            # Create keyword
            response = client.post(
                "/keywords",
                json={
                    "phrase": f"  {phrase.upper()}  ",
                    "country_code": "de",
                    "device": "desktop",
                },
            )

            assert response.status_code == 201

            data = response.json()

            assert data["phrase"] == phrase
            assert data["country_code"] == "DE"
            assert data["device"] == "desktop"

            # Duplicate keyword
            duplicate = client.post(
                "/keywords",
                json={
                    "phrase": phrase,
                    "country_code": "DE",
                    "device": "desktop",
                },
            )

            assert duplicate.status_code == 409

            # Same keyword, different device
            mobile = client.post(
                "/keywords",
                json={
                    "phrase": phrase,
                    "country_code": "DE",
                    "device": "mobile",
                },
            )

            assert mobile.status_code == 201

            # Invalid device
            invalid = client.post(
                "/keywords",
                json={
                    "phrase": phrase,
                    "country_code": "DE",
                    "device": "tablet",
                },
            )

            assert invalid.status_code == 422

    finally:
        app.dependency_overrides.pop(get_db, None)

def test_create_ranking_api(db_connection):

    def override_get_db():
        with Session(
            bind=db_connection,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        unique_id = uuid4().hex[:12]

        with TestClient(app) as client:

            # Create a test domain
            domain_response = client.post(
                "/domains",
                json={
                    "hostname": f"ranking-{unique_id}.example"
                },
            )

            assert domain_response.status_code == 201
            domain_id = domain_response.json()["id"]

            # Create a test keyword
            keyword_response = client.post(
                "/keywords",
                json={
                    "phrase": f"seo ranking {unique_id}",
                    "country_code": "DE",
                    "device": "desktop",
                },
            )

            assert keyword_response.status_code == 201
            keyword_id = keyword_response.json()["id"]

            payload = {
                "domain_id": domain_id,
                "keyword_id": keyword_id,
                "observed_on": "2026-10-20",
                "position": 5,
            }

            # Create a ranking
            response = client.post(
                "/rankings",
                json=payload,
            )

            assert response.status_code == 201
            assert response.json()["position"] == 5
            assert response.json()["domain_id"] == domain_id

            # Duplicate ranking
            duplicate = client.post(
                "/rankings",
                json=payload,
            )

            assert duplicate.status_code == 409

            # Invalid position
            invalid = client.post(
                "/rankings",
                json={**payload, "position": 101},
            )

            assert invalid.status_code == 422

            # Missing domain
            missing_domain = client.post(
                "/rankings",
                json={**payload, "domain_id": 999999999},
            )

            assert missing_domain.status_code == 404

            # Missing keyword
            missing_keyword = client.post(
                "/rankings",
                json={**payload, "keyword_id": 999999999},
            )

            assert missing_keyword.status_code == 404

            # Explicitly observed outside the Top 100
            unranked = client.post(
                "/rankings",
                json={
                    **payload,
                    "observed_on": "2026-10-21",
                    "position": None,
                },
            )

            assert unranked.status_code == 201
            assert unranked.json()["position"] is None

    finally:
        app.dependency_overrides.pop(get_db, None)

def test_domain_ranking_history_api(db_connection):

    def override_get_db():
        with Session(
            bind=db_connection,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        unique_id = uuid4().hex[:12]

        with TestClient(app) as client:
            domain_response = client.post(
                "/domains",
                json={
                    "hostname": f"history-{unique_id}.example"
                },
            )
            assert domain_response.status_code == 201
            domain_id = domain_response.json()["id"]

            keyword_response = client.post(
                "/keywords",
                json={
                    "phrase": f"ranking history {unique_id}",
                    "country_code": "DE",
                    "device": "desktop",
                },
            )
            assert keyword_response.status_code == 201
            keyword_id = keyword_response.json()["id"]

            # Create two observations
            for observed_on, position in [
                ("2026-10-18", 12),
                ("2026-10-19", 5),
            ]:
                response = client.post(
                    "/rankings",
                    json={
                        "domain_id": domain_id,
                        "keyword_id": keyword_id,
                        "observed_on": observed_on,
                        "position": position,
                    },
                )
                assert response.status_code == 201

            # Read ranking history
            response = client.get(
                f"/domains/{domain_id}/rankings"
            )

            assert response.status_code == 200

            history = response.json()

            assert len(history) == 2
            assert [item["position"] for item in history] == [
                5, 12
            ]
            assert all(
                item["keyword_id"] == keyword_id
                for item in history
            )

            # Test pagination
            page = client.get(
                f"/domains/{domain_id}/rankings",
                params={"limit": 1, "offset": 1},
            )

            assert page.status_code == 200
            assert len(page.json()) == 1
            assert page.json()[0]["position"] == 12

            # Domain does not exist
            missing = client.get(
                "/domains/999999999/rankings"
            )

            assert missing.status_code == 404

    finally:
        app.dependency_overrides.pop(get_db, None)

def test_ranking_changes_api(db_connection):

    def override_get_db():
        with Session(
            bind=db_connection,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        unique_id = uuid4().hex[:12]

        with TestClient(app) as client:
            # Create domain
            domain_response = client.post(
                "/domains",
                json={
                    "hostname": f"changes-{unique_id}.example"
                },
            )

            assert domain_response.status_code == 201
            domain_id = domain_response.json()["id"]

            keyword_ids = {}

            cases = [
                (
                    "improved",
                    [
                        ("2026-10-18", 12),
                        ("2026-10-20", 3),
                    ],
                ),
                (
                    "new",
                    [
                        ("2026-10-18", None),
                        ("2026-10-20", 8),
                    ],
                ),
                (
                    "incomplete",
                    [
                        ("2026-10-18", 4),
                    ],
                ),
            ]

            for label, observations in cases:
                keyword_response = client.post(
                    "/keywords",
                    json={
                        "phrase": f"{label} {unique_id}",
                        "country_code": "DE",
                        "device": "desktop",
                    },
                )

                assert keyword_response.status_code == 201

                keyword_id = keyword_response.json()["id"]
                keyword_ids[label] = keyword_id

                for observed_on, position in observations:
                    ranking_response = client.post(
                        "/rankings",
                        json={
                            "domain_id": domain_id,
                            "keyword_id": keyword_id,
                            "observed_on": observed_on,
                            "position": position,
                        },
                    )

                    assert ranking_response.status_code == 201

            url = f"/domains/{domain_id}/changes"

            response = client.get(
                url,
                params={
                    "from_date": "2026-10-18",
                    "to_date": "2026-10-20",
                },
            )

            assert response.status_code == 200

            results = response.json()

            assert len(results) == 2

            by_id = {
                item["keyword_id"]: item
                for item in results
            }

            improved = by_id[keyword_ids["improved"]]

            assert improved["movement"] == 9
            assert improved["status"] == "improved"

            new = by_id[keyword_ids["new"]]

            assert new["movement"] is None
            assert new["status"] == "new"

            # A missing observation is NOT a ranking loss
            assert keyword_ids["incomplete"] not in by_id

            # Invalid date order
            invalid = client.get(
                url,
                params={
                    "from_date": "2026-10-20",
                    "to_date": "2026-10-18",
                },
            )

            assert invalid.status_code == 422

            # Domain does not exist
            missing = client.get(
                "/domains/999999999/changes",
                params={
                    "from_date": "2026-10-18",
                    "to_date": "2026-10-20",
                },
            )

            assert missing.status_code == 404

    finally:
        app.dependency_overrides.pop(get_db, None)
