from __future__ import annotations

import asyncio
import logging
import socket
import time
from copy import deepcopy
from datetime import UTC
from datetime import datetime
from typing import Any
from typing import Dict
from urllib.parse import urlparse

import httpx
from opentelemetry import trace

from app.ai_search.providers.base import AISearchProvider

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class MeilisearchProvider(AISearchProvider):
    provider_name = "meilisearch"

    def __init__(self, *, base_url: str, baseline_index: str, candidate_index: str):
        self.base_url = base_url.rstrip("/")
        self.baseline_index = baseline_index
        self.candidate_index = candidate_index
        self._seed_lock = asyncio.Lock()
        self._seed_state: Dict[str, Any] = {
            "ready": False,
            "status": "unknown",
            "baseline_index": self.baseline_index,
            "shadow_index": self.candidate_index,
        }

    async def search(
        self,
        *,
        query_text: str,
        index_name: str,
        limit: int = 20,
        search_mode: str = "live",
    ) -> Dict[str, Any]:
        start_time = time.time()
        search_url = f"{self.base_url}/indexes/{index_name}/search"

        with tracer.start_as_current_span("ai_search.search") as span:
            span.set_attribute("search.backend", self.provider_name)
            span.set_attribute("search.index", index_name)
            span.set_attribute("search.mode", search_mode)
            span.set_attribute("search.query_length", len(query_text))

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        search_url,
                        json={"q": query_text, "limit": limit},
                        timeout=10.0,
                    )
            except httpx.RequestError as exc:
                latency_ms = (time.time() - start_time) * 1000
                logger.warning("AI search request failed: %s", exc)
                span.record_exception(exc)
                span.set_attribute("http.status_code", 503)
                return {
                    "query": query_text,
                    "index_name": index_name,
                    "results_count": 0,
                    "latency_ms": latency_ms,
                    "status_code": 503,
                    "raw_response": {
                        "error": "search_backend_unavailable",
                        "detail": str(exc),
                        "url": search_url,
                        "provider": self.provider_name,
                    },
                }

            latency_ms = (time.time() - start_time) * 1000

            try:
                data = response.json()
            except ValueError:
                data = {
                    "error": "invalid_json_response",
                    "body": response.text,
                }

            hits = data.get("hits", [])
            if not isinstance(hits, list):
                hits = []

            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("search.results_count", len(hits))

            return {
                "query": query_text,
                "index_name": index_name,
                "results_count": len(hits),
                "latency_ms": latency_ms,
                "status_code": response.status_code,
                "raw_response": data,
            }

    async def fetch_index_stats(self, index_name: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                response = await client.get(f"/indexes/{index_name}/stats", timeout=10.0)
        except Exception as exc:
            return {"status": "error", "payload": None, "error": str(exc)}
        if response.status_code == 404:
            return {"status": "index-missing", "payload": None, "error": f"Index '{index_name}' was not found."}
        try:
            response.raise_for_status()
        except Exception as exc:
            return {"status": "error", "payload": None, "error": str(exc)}
        return {"status": "ok", "payload": response.json(), "error": None}

    async def fetch_index_settings(self, index_name: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                response = await client.get(f"/indexes/{index_name}/settings", timeout=10.0)
        except Exception as exc:
            return {"status": "error", "payload": None, "error": str(exc)}
        if response.status_code == 404:
            return {"status": "index-missing", "payload": None, "error": f"Index '{index_name}' was not found."}
        try:
            response.raise_for_status()
        except Exception as exc:
            return {"status": "error", "payload": None, "error": str(exc)}
        return {"status": "ok", "payload": response.json(), "error": None}

    async def ensure_candidate_index_ready(self, force: bool = False) -> Dict[str, Any]:
        if self.candidate_index == self.baseline_index:
            return {
                "ready": True,
                "status": "same-as-baseline",
                "baseline_index": self.baseline_index,
                "shadow_index": self.candidate_index,
                "documents_synced": 0,
                "updated_at": self._timestamp(),
            }

        async with self._seed_lock:
            if self._seed_state.get("ready") and not force:
                return deepcopy(self._seed_state)

            state = {
                "ready": False,
                "status": "starting",
                "baseline_index": self.baseline_index,
                "shadow_index": self.candidate_index,
                "documents_synced": 0,
                "updated_at": self._timestamp(),
            }

            try:
                async with httpx.AsyncClient(base_url=self.base_url) as client:
                    baseline_response = await client.get(f"/indexes/{self.baseline_index}", timeout=10.0)
                    baseline_response.raise_for_status()

                    shadow_response = await client.get(f"/indexes/{self.candidate_index}", timeout=10.0)
                    if shadow_response.status_code == 404:
                        create_response = await client.post("/indexes", json={"uid": self.candidate_index}, timeout=10.0)
                        create_response.raise_for_status()
                        await self._wait_for_task(client, create_response.json()["taskUid"])
                        state["status"] = "created"
                    elif shadow_response.status_code >= 400:
                        shadow_response.raise_for_status()
                    else:
                        state["status"] = "existing"

                    settings_response = await client.get(f"/indexes/{self.baseline_index}/settings", timeout=10.0)
                    settings_response.raise_for_status()
                    patch_settings = await client.patch(
                        f"/indexes/{self.candidate_index}/settings",
                        json=settings_response.json(),
                        timeout=10.0,
                    )
                    patch_settings.raise_for_status()
                    await self._wait_for_task(client, patch_settings.json()["taskUid"])

                    documents = await self._fetch_documents(client, self.baseline_index)
                    if documents:
                        add_documents = await client.post(
                            f"/indexes/{self.candidate_index}/documents",
                            json=documents,
                            timeout=20.0,
                        )
                        add_documents.raise_for_status()
                        await self._wait_for_task(client, add_documents.json()["taskUid"], timeout_seconds=30.0)

                    shadow_stats = await self._fetch_index_stats_with_client(client, self.candidate_index)
                    state.update(
                        {
                            "ready": True,
                            "status": "ready",
                            "documents_synced": len(documents),
                            "number_of_documents": shadow_stats.get("numberOfDocuments", len(documents)),
                            "updated_at": self._timestamp(),
                        }
                    )
            except Exception as exc:
                state.update({"ready": False, "status": "error", "error": str(exc), "updated_at": self._timestamp()})

            self._seed_state.clear()
            self._seed_state.update(state)
            return deepcopy(state)

    def get_candidate_index_cached_state(self) -> Dict[str, Any]:
        return deepcopy(self._seed_state)

    async def health(self) -> Dict[str, Any]:
        parsed = urlparse(self.base_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 7700

        if not self._check_port(host, port):
            return {
                "type": "AI Search Engine",
                "provider": self.provider_name,
                "url": self.base_url,
                "status": "OFFLINE",
                "latency_ms": 0.0,
                "error": f"Cannot establish connection to {host}:{port}. Service is likely down.",
                "info": {},
            }

        start_time = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health", timeout=2.0)
                latency = (time.time() - start_time) * 1000
                if response.status_code == 200:
                    return {
                        "type": "AI Search Engine",
                        "provider": self.provider_name,
                        "url": self.base_url,
                        "status": "HEALTHY",
                        "latency_ms": latency,
                        "error": None,
                        "info": response.json(),
                    }
                return {
                    "type": "AI Search Engine",
                    "provider": self.provider_name,
                    "url": self.base_url,
                    "status": "DEGRADED",
                    "latency_ms": latency,
                    "error": f"Health endpoint returned status code {response.status_code}",
                    "info": {},
                }
        except Exception as exc:
            return {
                "type": "AI Search Engine",
                "provider": self.provider_name,
                "url": self.base_url,
                "status": "DEGRADED",
                "latency_ms": (time.time() - start_time) * 1000,
                "error": str(exc),
                "info": {},
            }

    async def _wait_for_task(self, client: httpx.AsyncClient, task_uid: int, timeout_seconds: float = 20.0) -> None:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while True:
            response = await client.get(f"/tasks/{task_uid}", timeout=10.0)
            response.raise_for_status()
            payload = response.json()
            status = payload.get("status")
            if status == "succeeded":
                return
            if status == "failed":
                raise RuntimeError(payload.get("error", {}).get("message", "Meilisearch task failed."))
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError(f"Timed out waiting for Meilisearch task {task_uid}.")
            await asyncio.sleep(0.35)

    async def _fetch_documents(self, client: httpx.AsyncClient, index_name: str) -> list[Dict[str, Any]]:
        documents: list[Dict[str, Any]] = []
        offset = 0
        batch_size = 1000
        while True:
            response = await client.get(
                f"/indexes/{index_name}/documents",
                params={"limit": batch_size, "offset": offset},
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()
            batch = payload if isinstance(payload, list) else payload.get("results", [])
            if not batch:
                break
            documents.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size
        return documents

    async def _fetch_index_stats_with_client(self, client: httpx.AsyncClient, index_name: str) -> Dict[str, Any]:
        response = await client.get(f"/indexes/{index_name}/stats", timeout=10.0)
        response.raise_for_status()
        return response.json()

    def _check_port(self, host: str, port: int, timeout: float = 2.0) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    def _timestamp(self) -> str:
        return datetime.now(tz=UTC).isoformat()
