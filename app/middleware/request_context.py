import logging
import time
from contextvars import ContextVar
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("sat_coach.http")

# Populated by RequestContextMiddleware.dispatch for the lifetime of a
# single request, so app.services.audit_service.AuditService can attach
# correlation/network context to an audit row without threading it
# through every service/route signature (see Phase 1.5 PR 5).
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_client_ip_ctx: ContextVar[str | None] = ContextVar("client_ip", default=None)
_user_agent_ctx: ContextVar[str | None] = ContextVar("user_agent", default=None)


def get_request_context() -> dict:
    return {
        "request_id": _request_id_ctx.get(),
        "ip_address": _client_ip_ctx.get(),
        "user_agent": _user_agent_ctx.get(),
    }


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request ID and emit privacy-safe request logs."""
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", uuid4().hex)
        request_id_token = _request_id_ctx.set(request_id)
        client_ip_token = _client_ip_ctx.set(request.client.host if request.client else None)
        user_agent_token = _user_agent_ctx.set(request.headers.get("user-agent"))
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            _request_id_ctx.reset(request_id_token)
            _client_ip_ctx.reset(client_ip_token)
            _user_agent_ctx.reset(user_agent_token)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_complete method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
            request_id,
        )
        return response
