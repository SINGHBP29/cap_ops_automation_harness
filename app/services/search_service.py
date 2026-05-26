from app.ai_search import get_ai_search_adapter


async def execute_search_against_index(query_text, index_name, limit=20, search_mode="live"):
    adapter = get_ai_search_adapter()
    return await adapter.search(
        query_text=query_text,
        index_name=index_name,
        limit=limit,
        search_mode=search_mode,
    )


async def execute_search(query_text):
    adapter = get_ai_search_adapter()
    return await adapter.search_baseline(
        query_text=query_text,
        limit=20,
        search_mode="live",
    )
