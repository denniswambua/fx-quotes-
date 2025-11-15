import json
import logging
from time import monotonic

from django.utils.deprecation import MiddlewareMixin


logger = logging.getLogger("app.request")


class StructuredLoggingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request._start_time = monotonic()

    def process_response(self, request, response):
        try:
            duration_ms = None
            if hasattr(request, "_start_time"):
                duration_ms = (monotonic() - request._start_time) * 1000

            payload = {
                "event": "http.request",
                "method": request.method,
                "path": request.get_full_path(),
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
                "remote_addr": request.META.get("REMOTE_ADDR"),
            }

            logger.info(json.dumps(payload))
        except Exception:  # pragma: no cover
            logger.exception("Structured logging middleware failure")

        return response
