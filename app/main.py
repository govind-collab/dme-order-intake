from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import DbSession, engine
from app.models import Base
from app.routers import auth


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="DME order intake", lifespan=lifespan)
app.include_router(auth.router)


@app.exception_handler(RequestValidationError)
async def validation_error_without_input(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    # Pydantic copies the rejected input into each error, and that input can be patient data
    details = [{"type": e["type"], "loc": e["loc"], "msg": e["msg"]} for e in error.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": details}
    )


@app.get("/health")
def health(db: DbSession, response: Response) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "database unavailable"}
    return {"status": "ok"}
