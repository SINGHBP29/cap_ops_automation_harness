import asyncio
import json
import os

import httpx

from app.services.intelligence_pipeline import IntelligencePipeline


async def fetch_json(client: httpx.AsyncClient, url: str):
    response = await client.get(url, timeout=10.0)
    response.raise_for_status()
    return response.json()


async def main():
    base_url = os.getenv("SIGNAL_ENGINE_URL", "http://localhost:8000").rstrip("/")

    async with httpx.AsyncClient() as client:
        signals_report = await fetch_json(client, f"{base_url}/signals")
        diagnostics_report = await fetch_json(client, f"{base_url}/diagnostics")

    pipeline = IntelligencePipeline()
    packet = pipeline.build_incident_packet(signals_report, diagnostics_report)
    print(json.dumps(packet, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
