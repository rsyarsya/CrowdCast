"""Request id and access log for every HTTP request.

Written as plain ASGI middleware so streaming responses (MJPEG, SSE) pass
through untouched.
"""

import logging
import re
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

access_logger = logging.getLogger("app.access")
error_logger = logging.getLogger("app.error")


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


class RequestContextMiddleware:
    """Reuses a well-formed incoming X-Request-ID or creates one, returns it in
    the response, and logs method, path, status, and time to first byte.

    The query string is never logged because it may hold a stream ticket.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(REQUEST_ID_HEADER.lower().encode(), b"").decode(
            "latin-1"
        )
        request_id = incoming if VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.perf_counter()
        status_code = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", [])
                message["headers"].append((REQUEST_ID_HEADER.lower().encode(), request_id.encode()))
                self._log(scope, status_code, started, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            self._log(scope, 500, started, request_id)
            raise

    @staticmethod
    def _log(scope: Scope, status_code: int, started: float, request_id: str) -> None:
        elapsed_ms = (time.perf_counter() - started) * 1000
        access_logger.info(
            "%s %s %d %.1fms rid=%s",
            scope["method"],
            scope["path"],
            status_code,
            elapsed_ms,
            request_id,
        )


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Unexpected errors: the stack trace goes to the log, the client gets a stable code."""
    request_id = request_id_of(request)
    error_logger.exception("Unhandled error on %s %s rid=%s", request.method, request.url.path, request_id)
    return JSONResponse(
        {"detail": "internal_error", "request_id": request_id},
        status_code=500,
        headers={REQUEST_ID_HEADER: request_id},
    )
