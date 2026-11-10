from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import DbSession, engine
from app.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="DME order intake", lifespan=lifespan)


@app.get("/health")
def health(db: DbSession, response: Response) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "database unavailable"}
    return {"status": "ok"}
