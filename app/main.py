"""FastAPI application: wiring, error handlers and the health check.

Owns app creation, logging setup, table creation on start, the upload size limit and in-memory
upload spool, the 422 handler that drops echoed input, the UploadRejected handler and /health.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.formparsers import MultiPartParser

from app.db import DbSession, engine
from app.errors import UploadRejected
from app.models import Base
from app.routers import auth, orders
from app.upload_limit import MAX_UPLOAD_REQUEST_BYTES, UploadSizeLimit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Starlette spools uploaded files over 1 MB to a temp file. Uploads are capped at this size,
# so raising the spool limit keeps every PDF in memory and off the disk.
MultiPartParser.spool_max_size = MAX_UPLOAD_REQUEST_BYTES


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create any missing tables when the app starts."""
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="DME order intake", lifespan=lifespan)
app.add_middleware(UploadSizeLimit)
app.include_router(auth.router)
app.include_router(orders.router)


@app.exception_handler(RequestValidationError)
async def validation_error_without_input(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    """Return a 422 listing each error's type, location and message, without the input.

    Pydantic copies the rejected input into every error, and that input can be patient data.
    """
    details = [{"type": e["type"], "loc": e["loc"], "msg": e["msg"]} for e in error.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": details}
    )


@app.exception_handler(UploadRejected)
async def upload_rejected(request: Request, error: UploadRejected) -> JSONResponse:
    """Return the upload error as JSON and log its status and cause type, never its content."""
    cause = type(error.__cause__).__name__ if error.__cause__ else "none"
    logger.warning("upload rejected status=%d cause=%s", error.status_code, cause)
    return JSONResponse(status_code=error.status_code, content={"detail": error.reason})


@app.get("/health")
def health(db: DbSession, response: Response) -> dict[str, str]:
    """Check that the service is up and the database answers.

    Returns `{"status": "ok"}`, or a 503 with `{"status": "database unavailable"}` when the
    database cannot be reached. Needs no token.
    """
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "database unavailable"}
    return {"status": "ok"}
