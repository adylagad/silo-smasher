from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
from neo4j.graph import Node, Path, Relationship

from .bedrock_embedder import BedrockEmbedder
from .config import GraphSettings


@dataclass
class SeedResult:
    element_id: str
    labels: list[str]
    score: float
    properties: dict[str, Any]


class Neo4jGraphStore:
    def __init__(self, settings: GraphSettings):
        self._settings = settings
        self._active_uri = settings.neo4j_uri
        self._driver = self._connect_with_fallback(settings)

    def close(self) -> None:
        self._driver.close()

    @property
    def active_uri(self) -> str:
        return self._active_uri

    def _connect_with_fallback(self, settings: GraphSettings):
        uri_candidates = [settings.neo4j_uri]
        parsed = urlparse(settings.neo4j_uri)
        if parsed.scheme == "neo4j+s":
            fallback = parsed._replace(scheme="neo4j+ssc")
            uri_candidates.append(urlunparse(fallback))

        last_error: Exception | None = None
        for uri in uri_candidates:
            driver = GraphDatabase.driver(
                uri,
                auth=(settings.neo4j_username, settings.neo4j_password),
            )
            try:
                driver.verify_connectivity()
                self._active_uri = uri
                return driver
            except ServiceUnavailable as exc:
                last_error = exc
                driver.close()
                continue

        raise RuntimeError(f"Unable to connect to Neo4j with URI candidates: {uri_candidates}") from last_error

    def ensure_schema(self, embedding_dimensions: int) -> None:
        statements = [
            "CREATE CONSTRAINT customer_id_unique IF NOT EXISTS FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE",
            "CREATE CONSTRAINT product_id_unique IF NOT EXISTS FOR (p:Product) REQUIRE p.product_id IS UNIQUE",
            "CREATE CONSTRAINT order_id_unique IF NOT EXISTS FOR (o:Order) REQUIRE o.order_id IS UNIQUE",
            "CREATE CONSTRAINT ticket_id_unique IF NOT EXISTS FOR (t:SupportTicket) REQUIRE t.ticket_id IS UNIQUE",
        ]
        with self._driver.session(database=self._settings.neo4j_database) as session:
            for statement in statements:
                session.run(statement).consume()
            index_statement = (
                f"CREATE VECTOR INDEX {self._settings.neo4j_vector_index} IF NOT EXISTS "
                "FOR (n:Retrievable) ON (n.embedding) "
                "OPTIONS {indexConfig: {"
                f"`vector.dimensions`: {int(embedding_dimensions)}, "
                "`vector.similarity_function`: 'cosine'}}"
            )
            session.run(
                index_statement,
            ).consume()

    def ingest_agent_context(
        self, context_document: dict[str, Any], embedder: BedrockEmbedder
    ) -> dict[str, int]:
        entities = context_document.get("entities", {})
        customers = entities.get("users", [])
        products = entities.get("products", [])
        orders = entities.get("purchase_events", [])

        customer_rows = [self._prepare_customer_row(customer, embedder) for customer in customers]
        product_rows = [self._prepare_product_row(product, embedder) for product in products]
        order_rows = [self._prepare_order_row(order, embedder) for order in orders]
        ticket_rows = [
            self._prepare_ticket_row(order, embedder)
            for order in orders
            if str(order.get("status", "")).lower() in {"returned", "unknown"}
        ]

        if customer_rows:
            self._upsert_customers(customer_rows)
        if product_rows:
            self._upsert_products(product_rows)
        if order_rows:
            self._upsert_orders(order_rows)
        if ticket_rows:
            self._upsert_tickets(ticket_rows)

        return {
            "customers": len(customer_rows),
            "products": len(product_rows),
            "orders": len(order_rows),
            "support_tickets": len(ticket_rows),
        }

    def find_seeds_by_embedding(
        self, query_embedding: list[float], top_k: int
    ) -> list[SeedResult]:
        with self._driver.session(database=self._settings.neo4j_database) as session:
            result = session.run(
                (
                    f"CALL db.index.vector.queryNodes('{self._settings.neo4j_vector_index}', "
                    "$top_k, $embedding) YIELD node, score "
                    "RETURN elementId(node) AS element_id, labels(node) AS labels, "
                    "score AS score, properties(node) AS properties "
                    "ORDER BY score DESC"
                ),
                top_k=top_k,
                embedding=query_embedding,
            )
            seed_rows: list[SeedResult] = []
            for record in result:
                properties = dict(record["properties"])
                properties.pop("embedding", None)
                seed_rows.append(
                    SeedResult(
                        element_id=str(record["element_id"]),
                        labels=list(record["labels"]),
                        score=float(record["score"]),
                        properties=properties,
                    )
                )
            return seed_rows

    def fetch_local_paths(self, seed_element_id: str, max_hops: int) -> list[Path]:
        capped_hops = max(1, min(max_hops, 3))
        query = (
            "MATCH (seed) WHERE elementId(seed) = $seed_element_id "
            f"MATCH path = (seed)-[*1..{capped_hops}]-(neighbor) "
            "RETURN path LIMIT 30"
        )
        with self._driver.session(database=self._settings.neo4j_database) as session:
            result = session.run(query, seed_element_id=seed_element_id)
            return [record["path"] for record in result]

    def fetch_customer_order_ticket_links(self, seed_element_id: str) -> list[dict[str, Any]]:
        query = (
            "MATCH (seed) WHERE elementId(seed) = $seed_element_id "
            "MATCH (c:Customer)-[:PLACED]->(o:Order)<-[:ABOUT_ORDER]-(t:SupportTicket) "
            "WHERE elementId(c) = elementId(seed) OR elementId(o) = elementId(seed) "
            "OR elementId(t) = elementId(seed) "
            "RETURN c.customer_id AS customer_id, c.full_name AS customer_name, "
            "o.order_id AS order_id, o.status AS order_status, "
            "t.ticket_id AS ticket_id, t.reason AS ticket_reason "
            "LIMIT 20"
        )
        with self._driver.session(database=self._settings.neo4j_database) as session:
            result = session.run(query, seed_element_id=seed_element_id)
            return [dict(record) for record in result]

    def _upsert_customers(self, rows: list[dict[str, Any]]) -> None:
        query = (
            "UNWIND $rows AS row "
            "MERGE (c:Customer {customer_id: row.customer_id}) "
            "SET c.full_name = row.full_name, "
            "    c.email = row.email, "
            "    c.age = row.age, "
            "    c.gender = row.gender, "
            "    c.language = row.language, "
            "    c.occupation = row.occupation, "
            "    c.address_json = row.address_json, "
            "    c.updated_at = row.updated_at, "
            "    c.embedding = row.embedding "
            "SET c:Retrievable"
        )
        with self._driver.session(database=self._settings.neo4j_database) as session:
            session.run(query, rows=rows).consume()

    def _upsert_products(self, rows: list[dict[str, Any]]) -> None:
        query = (
            "UNWIND $rows AS row "
            "MERGE (p:Product {product_id: row.product_id}) "
            "SET p.make = row.make, "
            "    p.model = row.model, "
            "    p.year = row.year, "
            "    p.price = row.price, "
            "    p.updated_at = row.updated_at, "
            "    p.embedding = row.embedding "
            "SET p:Retrievable"
        )
        with self._driver.session(database=self._settings.neo4j_database) as session:
            session.run(query, rows=rows).consume()

    def _upsert_orders(self, rows: list[dict[str, Any]]) -> None:
        query = (
            "UNWIND $rows AS row "
            "MATCH (c:Customer {customer_id: row.customer_id}) "
            "MATCH (p:Product {product_id: row.product_id}) "
            "MERGE (o:Order {order_id: row.order_id}) "
            "SET o.status = row.status, "
            "    o.timeline_json = row.timeline_json, "
            "    o.summary = row.summary, "
            "    o.embedding = row.embedding "
            "SET o:Retrievable "
            "MERGE (c)-[:PLACED]->(o) "
            "MERGE (o)-[:CONTAINS_PRODUCT]->(p)"
        )
        with self._driver.session(database=self._settings.neo4j_database) as session:
            session.run(query, rows=rows).consume()

    def _upsert_tickets(self, rows: list[dict[str, Any]]) -> None:
        query = (
            "UNWIND $rows AS row "
            "MATCH (c:Customer {customer_id: row.customer_id}) "
            "MATCH (o:Order {order_id: row.order_id}) "
            "MERGE (t:SupportTicket {ticket_id: row.ticket_id}) "
            "SET t.reason = row.reason, "
            "    t.status = row.status, "
            "    t.embedding = row.embedding "
            "SET t:Retrievable "
            "MERGE (c)-[:OPENED_TICKET]->(t) "
            "MERGE (t)-[:ABOUT_ORDER]->(o)"
        )
        with self._driver.session(database=self._settings.neo4j_database) as session:
            session.run(query, rows=rows).consume()

    @staticmethod
    def _prepare_customer_row(
        customer: dict[str, Any], embedder: BedrockEmbedder
    ) -> dict[str, Any]:
        address = customer.get("address") or {}
        summary = (
            f"Customer {customer.get('full_name')} ({customer.get('email')}) "
            f"age {customer.get('age')} occupation {customer.get('occupation')} "
            f"located in {address.get('city')}, {address.get('state')} {address.get('country_code')}."
        )
        embedding = embedder.embed_text(summary)
        return {
            "customer_id": customer.get("user_id"),
            "full_name": customer.get("full_name"),
            "email": customer.get("email"),
            "age": customer.get("age"),
            "gender": customer.get("gender"),
            "language": customer.get("language"),
            "occupation": customer.get("occupation"),
            "address_json": json.dumps(address, sort_keys=True, ensure_ascii=True),
            "updated_at": customer.get("updated_at"),
            "embedding": embedding,
        }

    @staticmethod
    def _prepare_product_row(
        product: dict[str, Any], embedder: BedrockEmbedder
    ) -> dict[str, Any]:
        summary = (
            f"Product {product.get('product_id')} {product.get('make')} {product.get('model')} "
            f"year {product.get('year')} priced {product.get('price')}."
        )
        embedding = embedder.embed_text(summary)
        return {
            "product_id": product.get("product_id"),
            "make": product.get("make"),
            "model": product.get("model"),
            "year": product.get("year"),
            "price": float(product.get("price", 0) or 0),
            "updated_at": product.get("updated_at"),
            "embedding": embedding,
        }

    @staticmethod
    def _prepare_order_row(order: dict[str, Any], embedder: BedrockEmbedder) -> dict[str, Any]:
        user = order.get("user") or {}
        product = order.get("product") or {}
        summary = (
            f"Order {order.get('event_id')} status {order.get('status')} for customer "
            f"{user.get('full_name')} ({user.get('email')}) purchasing {product.get('make')} "
            f"{product.get('model')} priced {product.get('price')}."
        )
        embedding = embedder.embed_text(summary)
        return {
            "order_id": order.get("event_id"),
            "customer_id": order.get("user_id"),
            "product_id": order.get("product_id"),
            "status": order.get("status"),
            "timeline_json": json.dumps(order.get("timeline") or {}, sort_keys=True, ensure_ascii=True),
            "summary": summary,
            "embedding": embedding,
        }

    @staticmethod
    def _prepare_ticket_row(order: dict[str, Any], embedder: BedrockEmbedder) -> dict[str, Any]:
        order_id = order.get("event_id")
        status = str(order.get("status", "")).lower()
        reason = "Return requested by customer" if status == "returned" else "Order requires support review"
        summary = f"Support ticket for order {order_id}. Reason: {reason}."
        embedding = embedder.embed_text(summary)
        return {
            "ticket_id": f"T-{order_id}",
            "customer_id": order.get("user_id"),
            "order_id": order_id,
            "reason": reason,
            "status": "open",
            "embedding": embedding,
        }

    @staticmethod
    def node_identifier(node: Node) -> str:
        if "customer_id" in node:
            return f"Customer:{node['customer_id']}"
        if "order_id" in node:
            return f"Order:{node['order_id']}"
        if "ticket_id" in node:
            return f"SupportTicket:{node['ticket_id']}"
        if "product_id" in node:
            return f"Product:{node['product_id']}"
        return f"Node:{node.id}"

    @staticmethod
    def relationship_reason(
        left: Node, relationship: Relationship, right: Node
    ) -> str:
        relation = relationship.type
        left_id = Neo4jGraphStore.node_identifier(left)
        right_id = Neo4jGraphStore.node_identifier(right)

        forward = relationship.start_node.id == left.id and relationship.end_node.id == right.id

        if relation == "PLACED":
            if forward:
                return f"{left_id} placed {right_id}"
            return f"{left_id} was placed by {right_id}"
        if relation == "CONTAINS_PRODUCT":
            if forward:
                return f"{left_id} contains {right_id}"
            return f"{left_id} is contained in {right_id}"
        if relation == "OPENED_TICKET":
            if forward:
                return f"{left_id} opened {right_id}"
            return f"{left_id} was opened by {right_id}"
        if relation == "ABOUT_ORDER":
            if forward:
                return f"{left_id} is about {right_id}"
            return f"{left_id} is referenced by {right_id}"
        if forward:
            return f"{left_id} connected to {right_id} via {relation}"
        return f"{left_id} connected from {right_id} via {relation}"
