from opentelemetry import trace

from app.detectors.error_detector import detect_search_errors
from app.detectors.latency_detector import detect_latency_issue
from app.detectors.zero_result import detect_zero_result
from app.kafka_client.producer import publish_signal
from app.services.ops_ledger import store_signal
from app.services.signal_envelope_service import SignalEnvelopeService

tracer = trace.get_tracer(__name__)
envelope_service = SignalEnvelopeService()

DETECTORS = [
    detect_zero_result,
    detect_latency_issue,
    detect_search_errors
]


async def process_search_event(search_event):
    with tracer.start_as_current_span("signals.process_search_event") as span:
        span.set_attribute("search.results_count", search_event["results_count"])
        span.set_attribute("search.status_code", search_event["status_code"])

        for detector in DETECTORS:
            signal = detector(search_event)

            if signal:
                enriched_signal = envelope_service.enrich_api_detector_signal(
                    signal=signal,
                    detector_name=detector.__name__,
                    search_event=search_event,
                )
                span.add_event(
                    "signal_detected",
                    {
                        "signal_type": enriched_signal.get("signal_type", "unknown"),
                        "severity": enriched_signal.get("severity", "info")
                    }
                )
                publish_signal(enriched_signal)
                await store_signal(enriched_signal)
