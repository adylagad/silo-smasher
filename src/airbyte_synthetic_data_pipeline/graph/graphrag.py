from __future__ import annotations

from typing import Any

from neo4j.graph import Path

from .bedrock_embedder import BedrockEmbedder
from .store import Neo4jGraphStore


class GraphRAGService:
    def __init__(self, store: Neo4jGraphStore, embedder: BedrockEmbedder):
        self._store = store
        self._embedder = embedder

    def answer_with_graph_context(
        self, question: str, top_k: int = 5, max_hops: int = 2
    ) -> dict[str, Any]:
        query_embedding = self._embedder.embed_text(question)
        seeds = self._store.find_seeds_by_embedding(query_embedding, top_k=top_k)

        seed_results: list[dict[str, Any]] = []
        for seed in seeds:
            local_paths = self._store.fetch_local_paths(
                seed_element_id=seed.element_id,
                max_hops=max_hops,
            )
            links = self._store.fetch_customer_order_ticket_links(seed.element_id)
            seed_results.append(
                {
                    "seed": {
                        "element_id": seed.element_id,
                        "labels": seed.labels,
                        "score": round(seed.score, 6),
                        "properties": seed.properties,
                    },
                    "why_connected_paths": self._render_paths(local_paths),
                    "customer_order_ticket_links": links,
                }
            )

        return {
            "question": question,
            "top_k": top_k,
            "max_hops": max_hops,
            "results": seed_results,
        }

    def _render_paths(self, paths: list[Path]) -> list[dict[str, Any]]:
        rendered: list[dict[str, Any]] = []
        for path in paths:
            node_chain = [self._store.node_identifier(node) for node in path.nodes]
            edge_reasons: list[str] = []
            for idx, relationship in enumerate(path.relationships):
                if idx + 1 >= len(path.nodes):
                    break
                edge_reasons.append(
                    self._store.relationship_reason(
                        left=path.nodes[idx],
                        relationship=relationship,
                        right=path.nodes[idx + 1],
                    )
                )
            rendered.append(
                {
                    "node_chain": node_chain,
                    "edge_reasons": edge_reasons,
                }
            )
        return rendered
