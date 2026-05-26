import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware

from app.monitoring.metrics import HTTP_REQUEST_DURATION_SECONDS
from app.monitoring.metrics import HTTP_REQUESTS_TOTAL

logger = logging.getLogger(__name__)

EXCLUDED_PATHS = {
    "/health",
    "/kafka-health",
    "/metrics",
}


class TelemetryMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request, call_next):

        start_time = time.time()

        response = await call_next(request)

        latency_seconds = time.time() - start_time
        path = request.url.path
        method = request.method
        status_code = str(response.status_code)

        if path not in EXCLUDED_PATHS:
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                path=path,
                status_code=status_code
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                path=path
            ).observe(latency_seconds)

        logger.info(
            "request_processed",
            extra={
                "path": path,
                "method": method,
                "latency_ms": latency_seconds * 1000,
                "status_code": response.status_code
            }
        )

        return response
