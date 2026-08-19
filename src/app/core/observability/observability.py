from time import perf_counter
from uuid import uuid4

import structlog
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from structlog.contextvars import bind_contextvars, clear_contextvars

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ("method", "route", "status"),
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ("method", "route"),
)


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = structlog.get_logger("http")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        clear_contextvars()
        candidate = Headers(scope=scope).get("x-request-id")
        request_id = (
            candidate
            if candidate and len(candidate) <= 128 and candidate.isascii()
            else uuid4().hex
        )
        bind_contextvars(request_id=request_id)

        started_at = perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message).append("x-request-id", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            method = scope.get("method", "UNKNOWN")
            duration = perf_counter() - started_at
            REQUEST_COUNT.labels(method=method, route=route, status=str(status_code)).inc()
            REQUEST_DURATION.labels(method=method, route=route).observe(duration)
            self.logger.info(
                "request_complete",
                method=method,
                route=route,
                status_code=status_code,
                duration_ms=round(duration * 1000, 2),
            )
            clear_contextvars()


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
