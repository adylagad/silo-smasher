from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from airbyte_synthetic_data_pipeline.finance import RevenueVarianceClient
from airbyte_synthetic_data_pipeline.graph import GraphRAGService, GraphSettings, Neo4jGraphStore
from airbyte_synthetic_data_pipeline.graph.bedrock_embedder import BedrockEmbedder
from airbyte_synthetic_data_pipeline.market_signals import ExternalNewsSearchClient
from airbyte_synthetic_data_pipeline.senso.client import SensoClient, SensoConfig
from airbyte_synthetic_data_pipeline.web_navigation import NavigatorClient


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
        self._navigator_client: NavigatorClient | None = None
        self._revenue_variance_client: RevenueVarianceClient | None = None
        self._external_news_client: ExternalNewsSearchClient | None = None
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
            "fetch_portal_report_with_web_navigation": ToolSpec(
                name="fetch_portal_report_with_web_navigation",
                description=(
                    "Use browser automation to log into an internal portal, find the latest PDF "
                    "report, and extract evidence when DB evidence is missing."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "portal_url": {"type": "string"},
                        "report_hint": {"type": "string"},
                        "task_prompt": {"type": "string"},
                        "require_auth": {"type": "boolean"},
                        "max_steps": {"type": "integer", "minimum": 10, "maximum": 150},
                        "timeout_seconds": {"type": "integer", "minimum": 30, "maximum": 1200},
                    },
                    "required": ["portal_url"],
                    "additionalProperties": False,
                },
                handler=self._fetch_portal_report_with_web_navigation,
            ),
            "analyze_revenue_variance": ToolSpec(
                name="analyze_revenue_variance",
                description=(
                    "Analyze revenue dip and determine whether it is seasonal or a potential "
                    "accounting anomaly with CFO-level explanation."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "current_revenue": {"type": "number"},
                        "prior_revenue": {"type": "number"},
                        "period_label": {"type": "string"},
                        "region": {"type": "string"},
                        "historical_change_pct": {"type": "number"},
                        "notes": {"type": "string"},
                    },
                    "required": ["current_revenue", "prior_revenue"],
                    "additionalProperties": False,
                },
                handler=self._analyze_revenue_variance,
            ),
            "search_external_economic_news": ToolSpec(
                name="search_external_economic_news",
                description=(
                    "Search external economic news for a country/region to explain revenue "
                    "movement with real-world context."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "country": {"type": "string"},
                        "query": {"type": "string"},
                        "hours_back": {"type": "integer", "minimum": 1, "maximum": 168},
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
                    },
                    "required": ["country"],
                    "additionalProperties": False,
                },
                handler=self._search_external_economic_news,
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

    def _ensure_navigator_client(self) -> NavigatorClient:
        if self._navigator_client:
            return self._navigator_client
        self._navigator_client = NavigatorClient.from_env()
        return self._navigator_client

    def _ensure_revenue_variance_client(self) -> RevenueVarianceClient:
        if self._revenue_variance_client:
            return self._revenue_variance_client
        self._revenue_variance_client = RevenueVarianceClient.from_env()
        return self._revenue_variance_client

    def _ensure_external_news_client(self) -> ExternalNewsSearchClient:
        if self._external_news_client:
            return self._external_news_client
        self._external_news_client = ExternalNewsSearchClient.from_env()
        return self._external_news_client

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

    def _fetch_portal_report_with_web_navigation(self, arguments: dict[str, Any]) -> dict[str, Any]:
        portal_url = str(arguments.get("portal_url", "")).strip()
        if not portal_url:
            return {"error": "portal_url is required"}

        report_hint = str(arguments.get("report_hint", "")).strip() or None
        task_prompt = str(arguments.get("task_prompt", "")).strip() or None
        require_auth = bool(arguments.get("require_auth", True))
        max_steps = int(arguments.get("max_steps", 75))
        timeout_seconds = int(arguments.get("timeout_seconds", 180))

        navigator = self._ensure_navigator_client()
        return navigator.fetch_latest_portal_report(
            portal_url=portal_url,
            report_hint=report_hint,
            task_prompt=task_prompt,
            require_auth=require_auth,
            max_steps=max_steps,
            timeout_seconds=timeout_seconds,
        )

    def _analyze_revenue_variance(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            current_revenue = float(arguments.get("current_revenue"))
            prior_revenue = float(arguments.get("prior_revenue"))
        except (TypeError, ValueError):
            return {
                "error": "current_revenue and prior_revenue must be numeric.",
                "arguments": arguments,
            }

        period_label = str(arguments.get("period_label", "")).strip() or None
        region = str(arguments.get("region", "")).strip() or None
        notes = str(arguments.get("notes", "")).strip() or None

        historical_change_raw = arguments.get("historical_change_pct")
        historical_change_pct: float | None = None
        if historical_change_raw is not None:
            try:
                historical_change_pct = float(historical_change_raw)
            except (TypeError, ValueError):
                return {
                    "error": "historical_change_pct must be numeric when provided.",
                    "arguments": arguments,
                }

        client = self._ensure_revenue_variance_client()
        return client.explain_revenue_dip(
            current_revenue=current_revenue,
            prior_revenue=prior_revenue,
            period_label=period_label,
            region=region,
            historical_change_pct=historical_change_pct,
            notes=notes,
        )

    def _search_external_economic_news(self, arguments: dict[str, Any]) -> dict[str, Any]:
        country = str(arguments.get("country", "")).strip()
        if not country:
            return {"error": "country is required"}

        query = str(arguments.get("query", "")).strip() or None
        hours_back = int(arguments.get("hours_back", 24))
        max_results = int(arguments.get("max_results", 5))

        client = self._ensure_external_news_client()
        return client.search_economic_news(
            country=country,
            query=query,
            hours_back=hours_back,
            max_results=max_results,
        )
