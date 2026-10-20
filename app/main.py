
from typing import Literal
from app.routers.domains import router as domains_router
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="SEO Ranking Analytics Engine",
    description="Backend API for SEO ranking analysis",
    version="0.1.0",
)

app.include_router(domains_router)

class RankingRequest(BaseModel):
    previous_position: int = Field(ge=1, le=100)
    current_position: int = Field(ge=1, le=100)


class RankingResponse(BaseModel):
    movement: int
    status: Literal["improved", "declined", "unchanged"]


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post(
    "/rankings/compare",
    response_model=RankingResponse,
)
def compare_rankings(data: RankingRequest):

    movement = (
        data.previous_position - data.current_position
    )

    if movement > 0:
        status = "improved"

    elif movement < 0:
        status = "declined"

    else:
        status = "unchanged"

    return {
        "movement": movement,
        "status": status,
    }
