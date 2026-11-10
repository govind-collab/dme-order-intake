from fastapi import HTTPException, status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.services.intake import MAX_PDF_BYTES

UPLOAD_PATH = "/orders/upload"
# Multipart framing adds a little on top of the file itself
MAX_UPLOAD_REQUEST_BYTES = MAX_PDF_BYTES + 64 * 1024


class UploadSizeLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] != UPLOAD_PATH:
            await self.app(scope, receive, send)
            return
        received = 0

        async def capped_receive() -> Message:
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > MAX_UPLOAD_REQUEST_BYTES:
                raise HTTPException(
                    status.HTTP_413_CONTENT_TOO_LARGE, "Upload is larger than 10 MB"
                )
            return message

        await self.app(scope, capped_receive, send)
