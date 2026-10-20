
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.models import Domain, Keyword, Ranking


def seed_demo() -> None:
    with Session(engine) as session:
        with session.begin():

            # 1. Find or create the domain
            domain = session.scalar(
                select(Domain).where(
                    Domain.hostname == "example.de"
                )
            )

            if domain is None:
                domain = Domain(hostname="example.de")
                session.add(domain)
                session.flush()

            # 2. Find or create the keyword
            keyword = session.scalar(
                select(Keyword).where(
                    Keyword.phrase == "seo agentur bonn",
                    Keyword.country_code == "DE",
                    Keyword.device == "desktop",
                )
            )

            if keyword is None:
                keyword = Keyword(
                    phrase="seo agentur bonn",
                    country_code="DE",
                    device="desktop",
                )
                session.add(keyword)
                session.flush()

            # 3. Insert daily ranking observations
            observations = [
                (date(2026, 10, 18), 12),
                (date(2026, 10, 19), 5),
            ]

            for observed_on, position in observations:
                existing = session.scalar(
                    select(Ranking.id).where(
                        Ranking.domain_id == domain.id,
                        Ranking.keyword_id == keyword.id,
                        Ranking.observed_on == observed_on,
                    )
                )

                if existing is None:
                    session.add(
                        Ranking(
                            domain_id=domain.id,
                            keyword_id=keyword.id,
                            observed_on=observed_on,
                            position=position,
                        )
                    )

    print("Demo data seed completed successfully!")


if __name__ == "__main__":
    seed_demo()
