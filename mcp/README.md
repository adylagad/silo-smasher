# MCP Server

This directory exposes Silo Smasher tools over Model Context Protocol (MCP).

## Exposed Tools

- `query_graph_connections`
- `get_senso_content`

## Run Locally

```bash
python mcp/server.py --transport stdio
```

Optional HTTP mode:

```bash
python mcp/server.py --transport streamable-http --host 127.0.0.1 --port 8001 --mount-path /mcp
```
