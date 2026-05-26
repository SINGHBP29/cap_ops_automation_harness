from app.state.feedback import get_threshold


def detect_latency_issue(search_event):
    latency_threshold_ms = int(get_threshold("request_latency_ms", 1000) or 1000)

    if search_event["latency_ms"] > latency_threshold_ms:

        return {
            "signal_type": "latency_spike",
            "severity": "critical",
            "capability": "search_api",
            "query": search_event["query"],
            "evidence": search_event
        }

    return None
