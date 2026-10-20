
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
