def detect_search_errors(search_event):

    if search_event["status_code"] >= 500:

        return {
            "signal_type": "search_api_failure",
            "severity": "critical",
            "capability": "search_platform",
            "query": search_event["query"],
            "evidence": search_event
        }

    return None