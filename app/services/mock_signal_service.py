from __future__ import annotations

from typing import Any
from typing import Dict

from app.mock_data import scenario_names
from app.mock_data import scenario_payload
from app.services.ops_event_ingestion_service import OpsSignalCaptureService


class MockSignalService:
    """Generate separated mock signals for demos without mixing them with API-generated ones."""

    def __init__(self, signal_capture_service: OpsSignalCaptureService | None = None) -> None:
        self._signal_capture_service = signal_capture_service or OpsSignalCaptureService()

    def list_scenarios(self) -> Dict[str, Any]:
        return {
            "origin": "mock_data",
            "scenarios": scenario_names(),
        }

    async def generate_scenario(self, name: str, derive_signals: bool = True) -> Dict[str, Any]:
        event = scenario_payload(name)
        result = await self._signal_capture_service.ingest_event(event, derive_signals=derive_signals)
        result["scenario"] = name
        result["origin"] = "mock_data"
        return result
