from collections import defaultdict

from app.monitoring.metrics import ZERO_RESULT_QUERIES_TOTAL
from app.state.feedback import get_threshold

zero_result_cache = defaultdict(int)


def detect_zero_result(search_event):
    threshold = int(get_threshold("zero_result_repeat_count", 3) or 3)

    if search_event["results_count"] == 0:

        query = search_event["query"]

        ZERO_RESULT_QUERIES_TOTAL.inc()

        zero_result_cache[query] += 1

        if zero_result_cache[query] >= threshold:

            return {
                "signal_type": "zero_result_cluster",
                "severity": "high",
                "capability": "semantic_search",
                "query": query,
                "evidence": search_event
            }

    return None
