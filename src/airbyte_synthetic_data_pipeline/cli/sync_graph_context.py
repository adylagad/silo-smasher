from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from airbyte_synthetic_data_pipeline.graph import GraphSettings, Neo4jGraphStore
from airbyte_synthetic_data_pipeline.graph.bedrock_embedder import BedrockEmbedder


def _latest_context_file(base_dir: Path) -> Path:
    context_dir = base_dir / "data" / "system_of_record" / "agent_context"
    files = sorted(context_dir.glob("context_*.json"))
    if not files:
        raise RuntimeError(
            f"No context files found in {context_dir}. Run build-agent-context first."
        )
    return files[-1]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest agent-ready context into Neo4j AuraDB with Bedrock embeddings."
    )
    parser.add_argument(
        "--context-file",
        default=None,
        help="Path to context JSON file. If omitted, latest file under data/system_of_record/agent_context is used.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = _parse_args()
    project_root = Path(__file__).resolve().parents[3]
    context_file = (
        Path(args.context_file).expanduser().resolve()
        if args.context_file
        else _latest_context_file(project_root)
    )

    context_document = json.loads(context_file.read_text(encoding="utf-8"))
    settings = GraphSettings.from_env()
    embedder = BedrockEmbedder(
        region_name=settings.aws_region,
        model_id=settings.bedrock_embedding_model_id,
    )
    probe_embedding = embedder.embed_text("embedding dimension probe")

    store = Neo4jGraphStore(settings)
    try:
        store.ensure_schema(embedding_dimensions=len(probe_embedding))
        counts = store.ingest_agent_context(context_document, embedder)
    finally:
        store.close()

    print(
        json.dumps(
            {
                "context_file": str(context_file),
                "neo4j_uri": store.active_uri,
                "neo4j_database": settings.neo4j_database,
                "vector_index": settings.neo4j_vector_index,
                "ingested": counts,
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
