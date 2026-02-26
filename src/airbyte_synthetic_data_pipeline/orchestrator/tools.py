from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from airbyte_synthetic_data_pipeline.graph import GraphRAGService, GraphSettings, Neo4jGraphStore
from airbyte_synthetic_data_pipeline.graph.bedrock_embedder import BedrockEmbedder
from airbyte_synthetic_data_pipeline.senso.client import SensoClient, SensoConfig


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler


class DiagnosticToolRuntime:
    def __init__(self):
        self._graph_store: Neo4jGraphStore | None = None
        self._graph_service: GraphRAGService | None = None
        self._senso_client: SensoClient | None = None
        self._tool_map: dict[str, ToolSpec] = {}
        self._init_tools()

    def close(self) -> None:
        if self._graph_store is not None:
            self._graph_store.close()
            self._graph_store = None

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            }
            for spec in self._tool_map.values()
        ]

    def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        spec = self._tool_map.get(tool_name)
        if not spec:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            return spec.handler(arguments)
        except Exception as exc:
            return {
                "error": str(exc),
                "tool_name": tool_name,
                "arguments": arguments,
            }

    def _init_tools(self) -> None:
        self._tool_map = {
            "query_graph_connections": ToolSpec(
                name="query_graph_connections",
                description=(
                    "Query the Neo4j GraphRAG store and return why entities are connected."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 15},
                        "max_hops": {"type": "integer", "minimum": 1, "maximum": 3},
                    },
                    "required": ["question"],
                    "additionalProperties": False,
                },
                handler=self._query_graph_connections,
            ),
            "get_senso_content": ToolSpec(
                name="get_senso_content",
                description=(
                    "Fetch a Senso content item by id for verified ground-truth context."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "content_id": {"type": "string"},
                    },
                    "required": ["content_id"],
                    "additionalProperties": False,
                },
                handler=self._get_senso_content,
            ),
            "get_latest_system_record_entries": ToolSpec(
                name="get_latest_system_record_entries",
                description=(
                    "Return recent local system-of-record manifest entries and optional file snippets."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer", "minimum": 1, "maximum": 20},
                        "include_context_preview": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                handler=self._get_latest_system_record_entries,
            ),
        }

    def _ensure_graph_service(self) -> GraphRAGService:
        if self._graph_service:
            return self._graph_service

        graph_settings = GraphSettings.from_env()
        embedder = BedrockEmbedder(
            region_name=graph_settings.aws_region,
            model_id=graph_settings.bedrock_embedding_model_id,
        )
        store = Neo4jGraphStore(graph_settings)
        self._graph_store = store
        self._graph_service = GraphRAGService(store=store, embedder=embedder)
        return self._graph_service

    def _ensure_senso_client(self) -> SensoClient:
        if self._senso_client:
            return self._senso_client
        senso_settings = SensoConfig.from_env()
        self._senso_client = SensoClient(senso_settings)
        return self._senso_client

    def _query_graph_connections(self, arguments: dict[str, Any]) -> dict[str, Any]:
        question = str(arguments.get("question", "")).strip()
        if not question:
            return {"error": "question is required"}
        top_k = int(arguments.get("top_k", 5))
        max_hops = int(arguments.get("max_hops", 2))
        service = self._ensure_graph_service()
        return service.answer_with_graph_context(
            question=question,
            top_k=max(1, min(top_k, 15)),
            max_hops=max(1, min(max_hops, 3)),
        )

    def _get_senso_content(self, arguments: dict[str, Any]) -> dict[str, Any]:
        content_id = str(arguments.get("content_id", "")).strip()
        if not content_id:
            return {"error": "content_id is required"}
        client = self._ensure_senso_client()
        detail = client.get_content(content_id)
        return {
            "id": detail.get("id"),
            "title": detail.get("title"),
            "summary": detail.get("summary"),
            "processing_status": detail.get("processing_status"),
            "created_at": detail.get("created_at"),
            "updated_at": detail.get("updated_at"),
            "text": detail.get("text"),
        }

    def _get_latest_system_record_entries(self, arguments: dict[str, Any]) -> dict[str, Any]:
        count = int(arguments.get("count", 3))
        include_context_preview = bool(arguments.get("include_context_preview", False))
        manifest_path = Path("data/system_of_record/manifest.jsonl")
        if not manifest_path.exists():
            return {"entries": [], "message": f"Manifest not found: {manifest_path}"}

        lines = manifest_path.read_text(encoding="utf-8").strip().splitlines()
        parsed = []
        for line in lines[-max(1, min(count, 20)) :]:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if include_context_preview:
                context_path = entry.get("context_path")
                if context_path:
                    path_obj = Path(context_path)
                    if path_obj.exists():
                        try:
                            context_obj = json.loads(path_obj.read_text(encoding="utf-8"))
                            entry["context_preview"] = {
                                "record_counts": context_obj.get("record_counts"),
                                "metrics": context_obj.get("facts", {}).get("metrics"),
                            }
                        except Exception:
                            entry["context_preview"] = {"error": "Unable to load context"}
            parsed.append(entry)
        return {"entries": parsed}

