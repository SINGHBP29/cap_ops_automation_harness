# AI Search Adapter

This package is the replaceable connection layer to the search backend.

Current backend:

- `Meilisearch` as a mock AI Search Engine

Future backend:

- any enterprise AI Search Engine that implements the same provider contract

## Files

- [adapter.py](/Users/bhsingh/Documents/Capstone_Demo3/app/ai_search/adapter.py)
  - stable application-facing wrapper
- [factory.py](/Users/bhsingh/Documents/Capstone_Demo3/app/ai_search/factory.py)
  - provider selection
- [models.py](/Users/bhsingh/Documents/Capstone_Demo3/app/ai_search/models.py)
  - connection configuration
- [providers/base.py](/Users/bhsingh/Documents/Capstone_Demo3/app/ai_search/providers/base.py)
  - provider contract
- [providers/meilisearch.py](/Users/bhsingh/Documents/Capstone_Demo3/app/ai_search/providers/meilisearch.py)
  - current implementation

## Rule

If code needs a Meilisearch-specific endpoint, keep it in `providers/`.

If code elsewhere needs to search, check health, or fetch index data, use the adapter.
