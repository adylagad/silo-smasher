from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_SQLITE_PATH = Path("data/system_of_record/sqlite/commerce.db")
DEFAULT_MANIFEST_PATH = Path("data/system_of_record/manifest.jsonl")
DEFAULT_FALLBACK_BUNDLE_PATH = Path("examples/synthetic_raw_bundle.json")

_READ_ONLY_START_PATTERN = re.compile(r"^(select|with|explain)\b", re.IGNORECASE)
_WRITE_OPERATION_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|vacuum|reindex|analyze|pragma)\b",
    re.IGNORECASE,
)


@dataclass
class StructuredQuerySettings:
    sqlite_path: Path
    max_rows_default: int
    max_rows_limit: int

    @classmethod
    def from_env(cls) -> "StructuredQuerySettings":
        sqlite_path = Path(
            os.getenv("STRUCTURED_QUERY_SQLITE_PATH", str(DEFAULT_SQLITE_PATH))
        ).expanduser()
        max_rows_default = int(os.getenv("STRUCTURED_QUERY_MAX_ROWS_DEFAULT", "100"))
        max_rows_limit = int(os.getenv("STRUCTURED_QUERY_MAX_ROWS_LIMIT", "500"))
        return cls(
            sqlite_path=sqlite_path,
            max_rows_default=max(1, max_rows_default),
            max_rows_limit=max(1, max_rows_limit),
        )


class StructuredQueryStore:
    def __init__(self, sqlite_path: Path):
        self._sqlite_path = sqlite_path.expanduser().resolve()
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    @property
    def sqlite_path(self) -> Path:
        return self._sqlite_path

    def has_data(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM purchases").fetchone()
            return bool(row and int(row["count"]) > 0)

    def sync_bundle(self, raw_bundle: dict[str, Any]) -> dict[str, int]:
        users = _bundle_rows(raw_bundle.get("users"))
        products = _bundle_rows(raw_bundle.get("products"))
        purchases = _bundle_rows(raw_bundle.get("purchases"))

        user_rows = [
            (
                _as_int(user.get("id")),
                _as_text(user.get("name")),
                _as_text(user.get("email")),
                _as_int(user.get("age")),
                _as_text(user.get("gender")),
                _as_text(user.get("language")),
                _as_text(user.get("occupation")),
                _as_text(_address(user).get("city")),
                _as_text(_address(user).get("state")),
                _as_text(_address(user).get("province")),
                _as_text(_address(user).get("postal_code")),
                _as_text(_address(user).get("country_code")),
                _as_text(user.get("created_at")),
                _as_text(user.get("updated_at")),
            )
            for user in users
        ]

        product_rows = [
            (
                _as_int(product.get("id")),
                _as_text(product.get("make")),
                _as_text(product.get("model")),
                _as_int(product.get("year")),
                _as_float(product.get("price")),
                _as_text(product.get("created_at")),
                _as_text(product.get("updated_at")),
            )
            for product in products
        ]

        purchase_rows = [
            (
                _as_int(purchase.get("id")),
                _as_int(purchase.get("user_id")),
                _as_int(purchase.get("product_id")),
                _as_text(purchase.get("added_to_cart_at")),
                _as_text(purchase.get("purchased_at")),
                _as_text(purchase.get("returned_at")),
                _as_text(purchase.get("created_at")),
                _as_text(purchase.get("updated_at")),
                _purchase_status(purchase),
            )
            for purchase in purchases
        ]

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self._connect() as conn:
            conn.execute("DELETE FROM purchases")
            conn.execute("DELETE FROM users")
            conn.execute("DELETE FROM products")
            conn.executemany(
                """
                INSERT INTO users (
                    id, name, email, age, gender, language, occupation,
                    city, state, province, postal_code, country_code,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                user_rows,
            )
            conn.executemany(
                """
                INSERT INTO products (
                    id, make, model, year, price, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                product_rows,
            )
            conn.executemany(
                """
                INSERT INTO purchases (
                    id, user_id, product_id, added_to_cart_at, purchased_at,
                    returned_at, created_at, updated_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                purchase_rows,
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO sync_metadata (key, value)
                VALUES ('last_sync_utc', ?)
                """,
                (now,),
            )

        return {
            "users": len(user_rows),
            "products": len(product_rows),
            "purchases": len(purchase_rows),
        }

    def execute_read_query(
        self,
        sql: str,
        params: dict[str, Any] | list[Any] | None = None,
        max_rows: int = 100,
        max_rows_limit: int = 500,
    ) -> dict[str, Any]:
        statement = _sanitize_sql(sql)
        bind_params = _normalize_params(params)
        row_limit = max(1, min(int(max_rows), int(max_rows_limit)))

        try:
            with self._connect() as conn:
                conn.execute("PRAGMA query_only = ON")
                cursor = conn.execute(statement, bind_params)
                description = cursor.description
                if description is None:
                    return {
                        "query": statement,
                        "columns": [],
                        "rows": [],
                        "row_count": 0,
                        "truncated": False,
                        "message": "Query executed but returned no tabular result.",
                    }

                columns = [str(col[0]) for col in description]
                fetched = cursor.fetchmany(row_limit + 1)
                truncated = len(fetched) > row_limit
                rows = fetched[:row_limit] if truncated else fetched
                return {
                    "query": statement,
                    "columns": columns,
                    "rows": [dict(row) for row in rows],
                    "row_count": len(rows),
                    "truncated": truncated,
                }
        except sqlite3.Error as exc:
            raise RuntimeError(f"SQL execution failed: {exc}") from exc

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._sqlite_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    age INTEGER,
                    gender TEXT,
                    language TEXT,
                    occupation TEXT,
                    city TEXT,
                    state TEXT,
                    province TEXT,
                    postal_code TEXT,
                    country_code TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY,
                    make TEXT,
                    model TEXT,
                    year INTEGER,
                    price REAL,
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS purchases (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    product_id INTEGER,
                    added_to_cart_at TEXT,
                    purchased_at TEXT,
                    returned_at TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    status TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );

                CREATE TABLE IF NOT EXISTS sync_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_purchases_user_id ON purchases(user_id);
                CREATE INDEX IF NOT EXISTS idx_purchases_product_id ON purchases(product_id);
                CREATE INDEX IF NOT EXISTS idx_purchases_purchased_at ON purchases(purchased_at);
                CREATE INDEX IF NOT EXISTS idx_purchases_returned_at ON purchases(returned_at);

                CREATE VIEW IF NOT EXISTS purchase_events_enriched AS
                SELECT
                    p.id AS purchase_id,
                    p.status,
                    p.user_id,
                    u.name AS user_name,
                    u.email AS user_email,
                    u.country_code,
                    p.product_id,
                    pr.make,
                    pr.model,
                    pr.price,
                    p.added_to_cart_at,
                    p.purchased_at,
                    p.returned_at,
                    p.created_at,
                    p.updated_at
                FROM purchases p
                LEFT JOIN users u ON u.id = p.user_id
                LEFT JOIN products pr ON pr.id = p.product_id;
                """
            )


def sync_bundle_to_sqlite(
    raw_bundle: dict[str, Any],
    sqlite_path: Path,
) -> dict[str, Any]:
    store = StructuredQueryStore(sqlite_path)
    counts = store.sync_bundle(raw_bundle)
    return {
        "sqlite_path": str(store.sqlite_path),
        "record_counts": counts,
    }


def bootstrap_sqlite_from_artifacts(
    store: StructuredQueryStore,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    fallback_bundle_path: Path = DEFAULT_FALLBACK_BUNDLE_PATH,
) -> dict[str, Any]:
    bundle: dict[str, Any] | None = None
    source: dict[str, Any] = {
        "manifest_path": str(manifest_path),
        "fallback_bundle_path": str(fallback_bundle_path),
    }

    manifest = manifest_path.expanduser().resolve()
    if manifest.exists():
        for line in reversed(manifest.read_text(encoding="utf-8").splitlines()):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            raw_snapshot_path = entry.get("raw_snapshot_path")
            if not raw_snapshot_path:
                continue
            snapshot = Path(str(raw_snapshot_path)).expanduser()
            if not snapshot.exists():
                continue
            bundle = _coerce_bundle(json.loads(snapshot.read_text(encoding="utf-8")))
            source.update(
                {
                    "source_type": "manifest_raw_snapshot",
                    "snapshot_path": str(snapshot.resolve()),
                    "snapshot_timestamp": entry.get("timestamp"),
                }
            )
            break

    if bundle is None:
        fallback = fallback_bundle_path.expanduser().resolve()
        if fallback.exists():
            bundle = _coerce_bundle(json.loads(fallback.read_text(encoding="utf-8")))
            source.update(
                {
                    "source_type": "fallback_bundle",
                    "snapshot_path": str(fallback),
                    "snapshot_timestamp": None,
                }
            )

    if bundle is None:
        return {
            "status": "skipped",
            "reason": "No bundle found to bootstrap SQLite.",
            "source": source,
            "sqlite_path": str(store.sqlite_path),
        }

    counts = store.sync_bundle(bundle)
    return {
        "status": "synced",
        "source": source,
        "sqlite_path": str(store.sqlite_path),
        "record_counts": counts,
    }


def _sanitize_sql(sql: str) -> str:
    statement = str(sql or "").strip()
    if not statement:
        raise RuntimeError("sql is required")

    if statement.endswith(";"):
        statement = statement[:-1].strip()
    if ";" in statement:
        raise RuntimeError("Only one SQL statement is allowed")

    lowered = statement.lower()
    if not _READ_ONLY_START_PATTERN.match(lowered):
        raise RuntimeError("Only read-only SELECT/WITH/EXPLAIN queries are allowed")

    if _WRITE_OPERATION_PATTERN.search(lowered):
        raise RuntimeError("Write SQL operations are blocked")

    return statement


def _normalize_params(params: dict[str, Any] | list[Any] | None) -> dict[str, Any] | list[Any]:
    if params is None:
        return {}
    if isinstance(params, dict):
        normalized: dict[str, Any] = {}
        for key, value in params.items():
            normalized[str(key)] = value
        return normalized
    if isinstance(params, list):
        return params
    raise RuntimeError("params must be an object or array")


def _coerce_bundle(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        if isinstance(payload.get("messages"), list):
            return _bundle_from_messages(payload["messages"])
        return {
            "users": _bundle_rows(payload.get("users")),
            "products": _bundle_rows(payload.get("products")),
            "purchases": _bundle_rows(payload.get("purchases")),
        }
    if isinstance(payload, list):
        return _bundle_from_messages(payload)
    raise RuntimeError("Expected bundle dict or Airbyte message list")


def _bundle_from_messages(messages: Iterable[Any]) -> dict[str, Any]:
    bundle: dict[str, list[dict[str, Any]]] = {
        "users": [],
        "products": [],
        "purchases": [],
    }
    for message in messages:
        if not isinstance(message, dict):
            continue
        if str(message.get("type", "")).lower() != "record":
            continue
        record = message.get("record")
        if not isinstance(record, dict):
            continue
        stream = str(record.get("stream", "")).lower()
        data = record.get("data")
        if stream in bundle and isinstance(data, dict):
            bundle[stream].append(data)
    return bundle


def _bundle_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _address(user: dict[str, Any]) -> dict[str, Any]:
    address = user.get("address")
    if isinstance(address, dict):
        return address
    return {}


def _purchase_status(purchase: dict[str, Any]) -> str:
    if purchase.get("returned_at"):
        return "returned"
    if purchase.get("purchased_at"):
        return "purchased"
    if purchase.get("added_to_cart_at"):
        return "carted"
    return "unknown"


def _as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
