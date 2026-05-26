from __future__ import annotations

import json
from typing import Any
from typing import Dict
from typing import Optional

import httpx

from app.config import settings
from app.services.intelligence_pipeline import IntelligencePipeline


class LLMIntelligencePipeline:
    def __init__(
        self,
        base_pipeline: Optional[IntelligencePipeline] = None,
        provider: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.base_pipeline = base_pipeline or IntelligencePipeline()
        self.provider = (provider or settings.LLM_PROVIDER or "none").lower().strip()
        self.api_url = (api_url or settings.LLM_API_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL or "llama3"

    async def build_incident_packet(
        self,
        signals_report: Dict[str, Any],
        diagnostics_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        packet = self.base_pipeline.build_incident_packet(signals_report, diagnostics_report)
        enrichment = await self._build_llm_enrichment(packet)
        packet["llm_enrichment"] = enrichment
        return packet

    async def _build_llm_enrichment(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        if self.provider == "none":
            return {
                "used": False,
                "status": "disabled",
                "provider": self.provider,
                "model": self.model,
                "content": None,
                "error": "LLM provider is disabled.",
            }

        prompt = self._build_prompt(packet)

        try:
            content = await self._query_model(prompt)
            parsed = self._parse_json(content)
            return {
                "used": True,
                "status": "ok",
                "provider": self.provider,
                "model": self.model,
                "content": parsed,
                "error": None,
            }
        except Exception as exc:
            return {
                "used": False,
                "status": "fallback",
                "provider": self.provider,
                "model": self.model,
                "content": None,
                "error": str(exc),
            }

    def _build_prompt(self, packet: Dict[str, Any]) -> str:
        return f"""You are helping generate the intelligence pipeline output for a search incident.
Use ONLY the evidence in the incident packet below. Do not invent missing data.
If the incident query looks synthetic or test-generated, say so explicitly.

Return JSON only with this exact schema:
{{
  "executive_summary": "string",
  "capability_reasoning": "string",
  "root_cause_narrative": "string",
  "candidate_fix": ["string", "string", "string"],
  "owner_notes": "string",
  "eval_focus": ["string", "string", "string"],
  "rollback_watchouts": ["string", "string"],
  "release_recommendation": "string"
}}

Incident packet:
{json.dumps(packet, indent=2)}
"""

    async def _query_model(self, prompt: str) -> str:
        if self.provider == "ollama":
            return await self._query_ollama(prompt)

        raise RuntimeError(
            f"Unsupported provider '{self.provider}' for the LLM incident pipeline. "
            "Use 'ollama' or set LLM_PROVIDER=none."
        )

    async def _query_ollama(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "stream": False,
            "format": "json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/chat",
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "").strip()

    def _parse_json(self, content: str) -> Dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise RuntimeError("LLM did not return valid JSON content.")
            return json.loads(content[start : end + 1])
