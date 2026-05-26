import asyncio
import json
import os

import httpx

from app.services.llm_intelligence_pipeline import LLMIntelligencePipeline


async def fetch_json(client: httpx.AsyncClient, url: str):
    response = await client.get(url, timeout=10.0)
    response.raise_for_status()
    return response.json()


async def main():
    base_url = os.getenv("SIGNAL_ENGINE_URL", "http://localhost:8000").rstrip("/")
    provider = os.getenv("LLM_PROVIDER", "ollama")
    model = os.getenv("LLM_MODEL", "llama3")
    api_url = os.getenv("LLM_API_URL", "http://localhost:11434")

    async with httpx.AsyncClient() as client:
        signals_report = await fetch_json(client, f"{base_url}/signals")
        diagnostics_report = await fetch_json(client, f"{base_url}/diagnostics")

    pipeline = LLMIntelligencePipeline(
        provider=provider,
        model=model,
        api_url=api_url,
    )
    packet = await pipeline.build_incident_packet(signals_report, diagnostics_report)
    print(json.dumps(packet, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
