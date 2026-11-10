"""Upload size limit enforced while the request body is still arriving.

Owns the cap on /orders/upload request bodies, so an oversized upload is cut off before it is
buffered in full.
"""

from fastapi import HTTPException, status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.services.intake import MAX_PDF_BYTES

UPLOAD_PATH = "/orders/upload"
# Multipart framing adds a little on top of the file itself
MAX_UPLOAD_REQUEST_BYTES = MAX_PDF_BYTES + 64 * 1024


class UploadSizeLimit:
    """ASGI middleware that answers 413 once an upload body passes the cap."""

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the ASGI app."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass the request on, counting the upload body's bytes as they arrive."""
        if scope["type"] != "http" or scope["path"] != UPLOAD_PATH:
            await self.app(scope, receive, send)
            return
        received = 0

        async def capped_receive() -> Message:
            """Return the next body message, or raise a 413 once the total passes the cap."""
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > MAX_UPLOAD_REQUEST_BYTES:
                raise HTTPException(
                    status.HTTP_413_CONTENT_TOO_LARGE, "Upload is larger than 10 MB"
                )
            return message

        await self.app(scope, capped_receive, send)
