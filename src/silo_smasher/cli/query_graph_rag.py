from __future__ import annotations

import argparse
import json

from dotenv import load_dotenv

from silo_smasher.graph import GraphRAGService, GraphSettings, Neo4jGraphStore
from silo_smasher.graph.bedrock_embedder import BedrockEmbedder


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run GraphRAG query against Neo4j AuraDB (vector seed + graph expansion)."
    )
    parser.add_argument("--question", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-hops", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = _parse_args()
    settings = GraphSettings.from_env()
    embedder = BedrockEmbedder(
        region_name=settings.aws_region,
        model_id=settings.bedrock_embedding_model_id,
    )
    store = Neo4jGraphStore(settings)
    try:
        service = GraphRAGService(store=store, embedder=embedder)
        answer = service.answer_with_graph_context(
            question=args.question,
            top_k=max(1, args.top_k),
            max_hops=max(1, args.max_hops),
        )
    finally:
        store.close()

    print(json.dumps(answer, indent=2, sort_keys=True, ensure_ascii=True))


if __name__ == "__main__":
    main()

