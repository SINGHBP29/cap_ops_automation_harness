from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client import generate_latest

from app.logging_config import configure_logging
from app.monitoring.capability_signals import router as capability_signal_router
from app.monitoring.controlled_release import router as controlled_release_router
from app.monitoring.feedback import router as feedback_router
from app.monitoring.health import router as health_router
from app.monitoring.incident_packet import router as incident_packet_router
from app.monitoring.mock_signals import router as mock_signal_router
from app.monitoring.ops_events import router as ops_events_router
from app.monitoring.operating_model import router as operating_model_router
from app.monitoring.operator_console import router as operator_console_router
from app.monitoring.reports import router as reports_router
from app.monitoring.rlm_analysis import router as rlm_analysis_router
from app.monitoring.shadow_testing import router as shadow_testing_router
from app.monitoring.signals import router as signals_router
from app.monitoring.temporal_release import router as temporal_release_router
from app.monitoring.traffic_router import router as traffic_router_router
from app.monitoring.traces import TelemetryMiddleware
from app.services.ops_ledger import recent_signals
from app.services.ops_ledger import store_signal
from app.services.search_ops_event_service import record_query_log_event
from app.services.signal_service import process_search_event
from app.services.traffic_router_service import route_search
from app.telemetry import configure_telemetry

configure_logging()

app = FastAPI(
    title="AI Search Signal Engine",
    version="1.0.0"
)

configure_telemetry(app)

app.add_middleware(TelemetryMiddleware)

app.include_router(health_router)
app.include_router(capability_signal_router)
app.include_router(feedback_router)
app.include_router(incident_packet_router)
app.include_router(signals_router)
app.include_router(mock_signal_router)
app.include_router(ops_events_router)
app.include_router(operating_model_router)
app.include_router(controlled_release_router)
app.include_router(operator_console_router)
app.include_router(reports_router)
app.include_router(rlm_analysis_router)
app.include_router(shadow_testing_router)
app.include_router(temporal_release_router)
app.include_router(traffic_router_router)


@app.get("/")
async def root():
    return {
        "service": "signal-engine",
        "status": "running"
    }


@app.get("/search")
async def search(query: str, request: Request):
    routing_key = (
        request.headers.get("x-user-id")
        or f"{request.client.host if request.client else 'anonymous'}:{query}"
    )
    routed = await route_search(query_text=query, routing_key=routing_key)
    search_event = routed["search_event"]
    await record_query_log_event(
        search_event=search_event,
        routing=routed["routing"],
        routing_key=routing_key,
        request_id=request.headers.get("x-request-id"),
        session_id=request.headers.get("x-session-id"),
        client_host=request.client.host if request.client else None,
    )
    await process_search_event(search_event)
    return {
        "search_event": search_event,
        "routing": routed["routing"],
    }

@app.get("/add-test-signal")
async def add_test_signal():
    dummy_signal = {"type": "test", "message": "This is a test signal"}
    await store_signal(dummy_signal)
    return {"added": dummy_signal}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/diagnostics")
async def run_system_diagnostics():
    from app.services.rca_engine import RCAEngine
    rca = RCAEngine()
    report = await rca.run_diagnostics()
    return report
