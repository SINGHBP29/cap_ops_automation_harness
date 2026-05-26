from __future__ import annotations

import argparse
import asyncio
import json

from app.services.rlm_incident_orchestrator import build_rlm_incident_analysis


async def main(use_llm: bool = False) -> None:
    analysis = await build_rlm_incident_analysis(use_llm=use_llm)
    print(json.dumps(analysis, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the RLM incident analysis JSON packet.")
    parser.add_argument("--use-llm", action="store_true", help="Enable Ollama enrichment.")
    args = parser.parse_args()
    asyncio.run(main(use_llm=args.use_llm))
