query_sessions = {}


def detect_reformulation(user_id, query):

    previous_query = query_sessions.get(user_id)

    query_sessions[user_id] = query

    if previous_query and previous_query != query:

        return {
            "signal_type": "query_reformulation",
            "severity": "medium",
            "capability": "ranking",
            "query": query,
            "evidence": {
                "previous_query": previous_query,
                "new_query": query
            }
        }

    return None