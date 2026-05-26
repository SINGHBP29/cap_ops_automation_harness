import logging
import os

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)
_telemetry_configured = False


def configure_telemetry(app: FastAPI):
    global _telemetry_configured

    if _telemetry_configured:
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    if not endpoint:
        base_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318").rstrip("/")
        endpoint = f"{base_endpoint}/v1/traces"

    resource = Resource.create(
        {
            SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "signal-engine")
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    span_processor = BatchSpanProcessor(
        OTLPSpanExporter(endpoint=endpoint),
        schedule_delay_millis=int(os.getenv("OTEL_BSP_SCHEDULE_DELAY", "1000"))
    )
    tracer_provider.add_span_processor(span_processor)

    trace.set_tracer_provider(tracer_provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)
    _telemetry_configured = True

    logger.info(
        "telemetry_configured",
        extra={
            "service_name": os.getenv("OTEL_SERVICE_NAME", "signal-engine"),
            "otlp_endpoint": endpoint
        }
    )
