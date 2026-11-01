from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.config import load_settings
from app.db import create_db_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_db_engine(load_settings())
    app.state.engine = engine
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="AuraMeme API", version="0.1.0", lifespan=lifespan)


class HealthResponse(BaseModel):
    status: Literal["ok"]


@app.get(
    "/health",
    response_model=HealthResponse,
    operation_id="health",
    summary="Health check (process readiness)",
    tags=["Health"],
)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
