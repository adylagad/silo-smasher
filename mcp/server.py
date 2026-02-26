from __future__ import annotations

import argparse
import atexit
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from silo_smasher.orchestrator.tools import DiagnosticToolRuntime


def _build_server(*, host: str, port: int, mount_path: str) -> FastMCP:
    app = FastMCP(
        name="Silo Smasher MCP",
        instructions=(
            "Use these tools to retrieve grounded graph relationships and "
            "system-of-record context for metric investigations."
        ),
        host=host,
        port=port,
        mount_path=mount_path,
        streamable_http_path=mount_path,
        json_response=True,
        log_level=os.getenv("MCP_LOG_LEVEL", "INFO").strip().upper(),
    )

    runtime = DiagnosticToolRuntime()
    atexit.register(runtime.close)

    @app.tool(
        name="query_graph_connections",
        description=(
            "Query Neo4j GraphRAG and explain why entities are connected for a question."
        ),
    )
    def query_graph_connections(
        question: str,
        top_k: int = 5,
        max_hops: int = 2,
    ) -> dict[str, Any]:
        return runtime.call(
            "query_graph_connections",
            {
                "question": question,
                "top_k": top_k,
                "max_hops": max_hops,
            },
        )

    @app.tool(
        name="get_senso_content",
        description="Fetch a Senso content item by id for verified ground-truth context.",
    )
    def get_senso_content(content_id: str) -> dict[str, Any]:
        return runtime.call(
            "get_senso_content",
            {
                "content_id": content_id,
            },
        )

    return app


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Silo Smasher MCP tool server.",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="MCP transport mode.",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "127.0.0.1"),
        help="Host for HTTP transports.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8001")),
        help="Port for HTTP transports.",
    )
    parser.add_argument(
        "--mount-path",
        default=os.getenv("MCP_MOUNT_PATH", "/mcp"),
        help="HTTP mount path used by streamable-http transport.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    app = _build_server(
        host=args.host,
        port=args.port,
        mount_path=args.mount_path,
    )
    app.run(
        transport=args.transport,
        mount_path=args.mount_path,
    )


if __name__ == "__main__":
    main()
