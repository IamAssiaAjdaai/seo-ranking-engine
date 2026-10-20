
from typing import Literal


RankingStatus = Literal[
    "improved",
    "declined",
    "unchanged",
    "new",
    "lost",
    "unranked",
]


def compare_positions(
    previous: int | None,
    current: int | None,
) -> tuple[int | None, RankingStatus]:

    if previous is None and current is None:
        return None, "unranked"

    if previous is None:
        return None, "new"

    if current is None:
        return None, "lost"

    movement = previous - current

    if movement > 0:
        return movement, "improved"

    if movement < 0:
        return movement, "declined"

    return 0, "unchanged"
