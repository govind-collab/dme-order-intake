"""Error type for uploads that cannot become an order.

Owns UploadRejected, which carries the HTTP status and a reason that is safe to show the client;
app.main turns it into a JSON response.
"""


class UploadRejected(Exception):
    """An upload was refused; its `reason` is safe to show and never holds document content."""

    def __init__(self, status_code: int, reason: str) -> None:
        """Keep the HTTP status code and the reason for the client."""
        super().__init__(reason)
        self.status_code = status_code
        self.reason = reason
