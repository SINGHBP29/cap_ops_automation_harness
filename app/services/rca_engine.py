import logging
import os
import socket
import time
import urllib.parse
from typing import Any
from typing import Dict
from typing import List

import httpx

from app.ai_search import get_ai_search_provider
from app.config import settings
from app.kafka_client.producer import get_producer
from app.services.ops_ledger import recent_signals

logger = logging.getLogger(__name__)

class RCAEngine:
    """
    Root Cause Analysis (RCA) Engine.
    Correlates issues across the AI search platform, Kafka, Postgres, Redis, and OpenTelemetry,
    analyzes recent signals, and outputs a diagnostic report.
    """

    def __init__(self):
        self.diagnostics = {}
        self.anomalies = []
        self.root_causes = []

    def _check_port(self, host: str, port: int, timeout: float = 1.0) -> bool:
        """Check if a TCP port is open."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    def _mask_url_password(self, url: str) -> str:
        """Mask password in a connection URL."""
        if not url:
            return ""
        parsed = urllib.parse.urlparse(url)
        if parsed.password:
            netloc = parsed.netloc.replace(f":{parsed.password}@", f":****@")
            return parsed._replace(netloc=netloc).geturl()
        return url

    async def diagnose_ai_search(self) -> Dict[str, Any]:
        """Perform health checks on the configured AI search engine."""
        provider = get_ai_search_provider()
        diagnostics = await provider.health()
        platform_type = diagnostics.get("type", provider.provider_name.title())
        status = diagnostics.get("status", "UNKNOWN")

        if status == "OFFLINE":
            self.anomalies.append({
                "source": platform_type,
                "type": "CONNECTION_FAILURE",
                "severity": "CRITICAL",
                "message": f"{platform_type} is unreachable."
            })
            self.root_causes.append({
                "issue": f"{platform_type} is offline",
                "cause": "The AI search platform process is not running or its endpoint is blocked.",
                "remedy": "Start the configured AI search engine or update the provider/base URL settings."
            })
        elif status == "DEGRADED":
            self.anomalies.append({
                "source": platform_type,
                "type": "HTTP_FAILURE",
                "severity": "HIGH",
                "message": f"{platform_type} is responding but returned errors: {diagnostics.get('error')}."
            })

        return {
            "type": platform_type,
            "provider": diagnostics.get("provider", provider.provider_name),
            "url": self._mask_url_password(str(diagnostics.get("url", settings.AI_SEARCH_BASE_URL))),
            "status": status,
            "latency_ms": diagnostics.get("latency_ms", 0.0),
            "error": diagnostics.get("error"),
            "info": diagnostics.get("info", {}),
        }

    async def diagnose_kafka(self) -> Dict[str, Any]:
        """Check Kafka bootstrap servers connectivity."""
        status = "UNKNOWN"
        error_msg = None
        
        bootstrap_servers = settings.KAFKA_BOOTSTRAP_SERVERS
        # Parse host and port
        parts = bootstrap_servers.split(",")
        primary = parts[0].strip()
        host_port = primary.split(":")
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 9092

        is_port_open = self._check_port(host, port, timeout=2.0)
        
        active_producer = get_producer()

        if active_producer is not None and active_producer.bootstrap_connected():
            status = "CONNECTED"
        elif is_port_open:
            status = "PORT_OPEN_PRODUCER_FAILED"
            error_msg = "Kafka port 9092 is open, but producer initialization failed. Check credentials or bootstrap configuration."
            self.anomalies.append({
                "source": "Kafka",
                "type": "PRODUCER_INITIALIZATION_ERROR",
                "severity": "WARNING",
                "message": "Kafka port is reachable but connection failed."
            })
        else:
            status = "OFFLINE"
            error_msg = f"Cannot connect to Kafka bootstrap server at {host}:{port}."
            self.anomalies.append({
                "source": "Kafka",
                "type": "CONNECTION_FAILURE",
                "severity": "WARNING",
                "message": "Kafka broker is unreachable. Observability signals are not published to the cluster."
            })
            self.root_causes.append({
                "issue": "Kafka Broker Offline",
                "cause": "Kafka broker is down or not running.",
                "remedy": "Start Kafka using `docker compose up -d` or verify the bootstrap settings."
            })

        return {
            "bootstrap_servers": bootstrap_servers,
            "status": status,
            "error": error_msg
        }

    async def diagnose_postgres(self) -> Dict[str, Any]:
        """Check PostgreSQL database connection status."""
        status = "UNKNOWN"
        error_msg = None
        
        db_url = settings.DATABASE_URL
        try:
            parsed = urllib.parse.urlparse(db_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 5432
            
            is_port_open = self._check_port(host, port, timeout=2.0)
            if is_port_open:
                status = "REACHABLE"
            else:
                status = "OFFLINE"
                error_msg = f"Postgres database at {host}:{port} is unreachable."
                self.anomalies.append({
                    "source": "PostgreSQL",
                    "type": "CONNECTION_FAILURE",
                    "severity": "HIGH",
                    "message": "PostgreSQL database port is closed. Application persistence or operations ledger may fail if DB is required."
                })
                self.root_causes.append({
                    "issue": "PostgreSQL Database Offline",
                    "cause": f"Postgres daemon is not running on {host}:{port}.",
                    "remedy": "Start PostgreSQL container/service or verify the connection string."
                })
        except Exception as e:
            status = "CONFIG_ERROR"
            error_msg = f"Failed to parse database URL: {e}"

        return {
            "url": self._mask_url_password(db_url),
            "status": status,
            "error": error_msg
        }

    async def diagnose_redis(self) -> Dict[str, Any]:
        """Check Redis caching service connection status."""
        status = "UNKNOWN"
        error_msg = None
        
        redis_url = settings.REDIS_URL
        try:
            parsed = urllib.parse.urlparse(redis_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 6379
            
            is_port_open = self._check_port(host, port, timeout=2.0)
            if is_port_open:
                status = "REACHABLE"
            else:
                status = "OFFLINE"
                error_msg = f"Redis cache at {host}:{port} is unreachable."
                self.anomalies.append({
                    "source": "Redis",
                    "type": "CONNECTION_FAILURE",
                    "severity": "WARNING",
                    "message": "Redis caching service port is closed. Performance optimization or session store is disabled."
                })
        except Exception as e:
            status = "CONFIG_ERROR"
            error_msg = f"Failed to parse Redis URL: {e}"

        return {
            "url": self._mask_url_password(redis_url),
            "status": status,
            "error": error_msg
        }

    async def diagnose_telemetry(self) -> Dict[str, Any]:
        """Check OpenTelemetry OTLP trace exporter target status."""
        status = "UNKNOWN"
        error_msg = None
        
        # Checking local Jaeger / Otel collector default port 4318 (HTTP)
        host = "localhost"
        port = 4318
        
        is_port_open = self._check_port(host, port, timeout=1.0)
        if is_port_open:
            status = "REACHABLE"
        else:
            status = "OFFLINE"
            error_msg = f"OpenTelemetry collector is not listening on {host}:{port} (HTTP OTLP)."
            self.anomalies.append({
                "source": "OpenTelemetry",
                "type": "EXPORTER_FAILURE",
                "severity": "INFO",
                "message": f"OTLP Span exporter endpoint http://{host}:{port}/v1/traces is down. Spans are not collected."
            })
            self.root_causes.append({
                "issue": "OpenTelemetry Collector Down",
                "cause": "No OTLP collector is listening on port 4318.",
                "remedy": "Start Jaeger (`docker run -d -p 16686:16686 -p 4318:4318 jaegertracing/all-in-one`) or OpenTelemetry Collector."
            })

        return {
            "endpoint": f"http://{host}:{port}/v1/traces",
            "status": status,
            "error": error_msg
        }

    async def diagnose_temporal(self) -> Dict[str, Any]:
        """Check Temporal workflow service connectivity."""
        status = "UNKNOWN"
        error_msg = None

        address = settings.TEMPORAL_ADDRESS
        if not settings.TEMPORAL_ENABLED:
            return {
                "address": address,
                "status": "DISABLED",
                "error": None,
            }

        if "://" in address:
            parsed = urllib.parse.urlparse(address)
            host = parsed.hostname or "localhost"
            port = parsed.port or 7233
        else:
            host_port = address.split(":")
            host = host_port[0] or "localhost"
            port = int(host_port[1]) if len(host_port) > 1 else 7233

        is_port_open = self._check_port(host, port, timeout=1.0)
        if is_port_open:
            status = "REACHABLE"
        else:
            status = "OFFLINE"
            error_msg = f"Temporal workflow service is unreachable at {host}:{port}."
            self.anomalies.append({
                "source": "Temporal",
                "type": "WORKFLOW_SERVICE_UNAVAILABLE",
                "severity": "WARNING",
                "message": "Temporal is down, so approval and rollout orchestration fall back to local app logic."
            })
            self.root_causes.append({
                "issue": "Temporal Workflow Service Offline",
                "cause": "Temporal server is not running or its gRPC port is unavailable.",
                "remedy": "Start the Temporal server and worker, then recheck the orchestration health."
            })

        return {
            "address": address,
            "status": status,
            "error": error_msg
        }

    def analyze_signals(self) -> Dict[str, Any]:
        """Analyze recent signals to detect clusters and anomalies."""
        analysis = {
            "total_signals": len(recent_signals),
            "by_type": {},
            "by_severity": {},
            "common_queries": {},
            "correlations": []
        }

        for sig in recent_signals:
            # We skip dummy or simple test signals if they don't follow standard format
            sig_type = sig.get("signal_type") or sig.get("type") or "unknown"
            severity = sig.get("severity") or "info"
            query = sig.get("query") or ""

            analysis["by_type"][sig_type] = analysis["by_type"].get(sig_type, 0) + 1
            analysis["by_severity"][severity] = analysis["by_severity"].get(severity, 0) + 1
            if query:
                analysis["common_queries"][query] = analysis["common_queries"].get(query, 0) + 1

        # Check for Zero-Result Cluster Correlation
        zero_result_count = analysis["by_type"].get("zero_result_cluster", 0)
        if zero_result_count > 0:
            top_queries = sorted(analysis["common_queries"].items(), key=lambda x: x[1], reverse=True)
            queries_str = ", ".join([f"'{q}' ({c} times)" for q, c in top_queries[:3]])
            self.anomalies.append({
                "source": "Zero Result Detector",
                "type": "ZERO_RESULT_CLUSTER",
                "severity": "HIGH",
                "message": f"Detected {zero_result_count} zero-result search clusters. Affected queries: {queries_str}."
            })
            self.root_causes.append({
                "issue": "Search Index Mismatch or Missing Documents",
                "cause": "Queries returned zero hits multiple times. Either the search index does not contain items matching these terms, or the search vocabulary needs adjustment.",
                "remedy": "Verify if the search index is populated. Implement query suggestions or synonym matching."
            })

        # Check for Latency Spikes Correlation
        latency_spike_count = analysis["by_type"].get("latency_spike", 0)
        if latency_spike_count > 0:
            self.anomalies.append({
                "source": "Latency Detector",
                "type": "LATENCY_SPIKES",
                "severity": "CRITICAL",
                "message": f"Detected {latency_spike_count} critical latency spikes (> {settings.LATENCY_THRESHOLD_MS}ms) in search requests."
            })
            self.root_causes.append({
                "issue": "Slow Query Latency Spike",
                "cause": "Meilisearch/Elasticsearch query took longer than the acceptable threshold.",
                "remedy": "Analyze query performance, configure Meilisearch index search settings, or check CPU/Memory constraints."
            })

        # Check for Search API Failures
        api_failure_count = analysis["by_type"].get("search_api_failure", 0)
        if api_failure_count > 0:
            self.anomalies.append({
                "source": "Error Detector",
                "type": "SEARCH_API_FAILURE",
                "severity": "CRITICAL",
                "message": f"Detected {api_failure_count} Search API HTTP 500+ failures."
            })
            self.root_causes.append({
                "issue": "Search Backend Server Error",
                "cause": "Meilisearch/Elasticsearch returned a 5xx response code to our application.",
                "remedy": "Check Meilisearch logs to see if there's an internal error, bad configuration, or missing index."
            })

        return analysis

    async def run_diagnostics(self, run_llm: bool = True) -> Dict[str, Any]:
        """Run all diagnostics and synthesize final root causes."""
        # Reset lists
        self.anomalies = []
        self.root_causes = []

        # Run checks
        ai_search_diag = await self.diagnose_ai_search()
        kafka_diag = await self.diagnose_kafka()
        postgres_diag = await self.diagnose_postgres()
        redis_diag = await self.diagnose_redis()
        otel_diag = await self.diagnose_telemetry()
        temporal_diag = await self.diagnose_temporal()
        
        # Analyze signals
        signal_diag = self.analyze_signals()

        # Build overall system rating
        total_anomalies = len(self.anomalies)
        critical_count = sum(1 for a in self.anomalies if a["severity"] == "CRITICAL")
        high_count = sum(1 for a in self.anomalies if a["severity"] == "HIGH")
        
        if critical_count > 0:
            health_rating = "CRITICAL"
        elif high_count > 0:
            health_rating = "DEGRADED"
        elif total_anomalies > 0:
            health_rating = "WARNING"
        else:
            health_rating = "HEALTHY"

        self.diagnostics = {
            "timestamp": time.time(),
            "health_rating": health_rating,
            "services": {
                "search_backend": ai_search_diag,
                "kafka": kafka_diag,
                "postgres": postgres_diag,
                "redis": redis_diag,
                "opentelemetry": otel_diag,
                "temporal": temporal_diag,
            },
            "signals_summary": signal_diag,
            "detected_anomalies": self.anomalies,
            "identified_root_causes": self.root_causes,
            "ai_explanation": None
        }

        if run_llm:
            try:
                from app.services.llm_client import LLMClient
                llm = LLMClient()
                self.diagnostics["ai_explanation"] = await llm.generate_rca_explanation(self.diagnostics)
            except Exception as e:
                logger.warning(f"Failed to generate LLM explanation: {e}")
                self.diagnostics["ai_explanation"] = f"AI Diagnosis unavailable due to error: {e}"
        
        return self.diagnostics
