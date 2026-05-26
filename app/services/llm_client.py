import logging
import httpx
from typing import Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)

class LLMClient:
    """
    Highly flexible LLM client that translates raw structured JSON diagnostics 
    reports into high-quality, actionable, natural language Root Cause analyses.
    Supports Ollama (default), OpenAI, Gemini, or standalone offline grace fallback.
    """

    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower().strip()
        self.api_url = settings.LLM_API_URL.strip()
        self.model = settings.LLM_MODEL.strip()
        self.api_key = settings.LLM_API_KEY.strip()

    def _build_rca_prompt(self, report: Dict[str, Any]) -> str:
        """Construct the prompt sent to the LLM."""
        return f"""You are an elite Site Reliability Engineer (SRE) and Systems Architect.
Analyze this structured JSON System Diagnostics report gathered from our observability platform:

SYSTEM RATING: {report.get('health_rating')}
SERVICES STATUS:
{report.get('services')}
ANOMALIES REGISTERED:
{report.get('detected_anomalies')}
PRE-IDENTIFIED CAUSES:
{report.get('identified_root_causes')}

Please perform a comprehensive Root Cause Analysis (RCA) and respond in clean Markdown with:
1. 🚨 **High-Level Diagnosis**: A 2-sentence executive summary of the primary outage or bottleneck.
2. 🔬 **Failure Chain Analysis**: A bulleted explanation of how the failure in one component propagates to affect others (e.g. Meilisearch offline causing search API HTTP 500s).
3. 🔧 **Step-by-Step Resolution Playbook**: Concrete terminal commands to run on a macOS system to fix the failures immediately. Use clean command blocks.
Keep your tone highly professional, precise, and concise. Avoid preambles.
"""

    async def _query_ollama(self, prompt: str) -> str:
        """Query a local Ollama instance using the direct api/generate endpoint."""
        url = f"{self.api_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=20.0)
            if response.status_code == 200:
                data = response.json()
                return data.get("message", {}).get("content", "").strip()
            else:
                raise RuntimeError(f"Ollama returned HTTP error: {response.status_code} - {response.text}")

    async def _query_openai_compatible(self, prompt: str) -> str:
        """Query an OpenAI-compatible completion API (or Ollama's /v1/chat/completions endpoint)."""
        url = f"{self.api_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=20.0)
            if response.status_code == 200:
                data = response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            else:
                raise RuntimeError(f"OpenAI-compatible endpoint returned HTTP error: {response.status_code}")

    async def _query_gemini(self, prompt: str) -> str:
        """Query Google Gemini API directly using a standard HTTP client."""
        if not self.api_key:
            raise ValueError("Gemini API Key is missing. Please set LLM_API_KEY environment variable.")
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=25.0)
            if response.status_code == 200:
                data = response.json()
                return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            else:
                raise RuntimeError(f"Gemini API returned HTTP error: {response.status_code} - {response.text}")

    async def generate_rca_explanation(self, report: Dict[str, Any]) -> str:
        """
        Executes LLM-based root cause analysis.
        Gracefully handles timeouts or unreachable engines to prevent crashing.
        """
        if self.provider == "none":
            return "*AI-based Root Cause Analysis is currently disabled (LLM_PROVIDER is set to 'none').*"

        prompt = self._build_rca_prompt(report)
        logger.info(f"Generating LLM RCA explanation using provider: {self.provider}")

        try:
            if self.provider == "ollama":
                # Check direct ollama chat port
                return await self._query_ollama(prompt)
            elif self.provider in ("openai", "openai-compatible"):
                return await self._query_openai_compatible(prompt)
            elif self.provider == "gemini":
                return await self._query_gemini(prompt)
            else:
                return f"*Unsupported LLM provider: {self.provider}. Please choose 'ollama', 'openai', 'gemini' or 'none'.*"
        except Exception as e:
            logger.warning(f"LLM RCA query failed or timed out: {e}")
            return f"""⚠️  **AI-assisted RCA Diagnosis Unavailable**
*The LLM provider '{self.provider}' (model: '{self.model}') could not be reached.*
*Reason: {str(e)}*

💡 **Troubleshooting local LLM:**
1. Ensure Ollama is running locally: `pgrep ollama` or look at your macOS menu bar.
2. Verify you have downloaded the '{self.model}' model: `ollama run {self.model}`
3. To disable AI diagnostics entirely, configure `LLM_PROVIDER=none` in your environment.
"""
