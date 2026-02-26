from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class GraphSettings:
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    neo4j_database: str
    neo4j_vector_index: str
    aws_region: str
    bedrock_embedding_model_id: str

    @classmethod
    def from_env(cls) -> "GraphSettings":
        uri = os.getenv("NEO4J_URI")
        username = os.getenv("NEO4J_USERNAME")
        password = os.getenv("NEO4J_PASSWORD")
        aws_region = os.getenv("AWS_REGION")

        missing: list[str] = []
        if not uri:
            missing.append("NEO4J_URI")
        if not username:
            missing.append("NEO4J_USERNAME")
        if not password:
            missing.append("NEO4J_PASSWORD")
        if not aws_region:
            missing.append("AWS_REGION")
        if missing:
            raise RuntimeError(
                "Missing required environment variables: " + ", ".join(sorted(missing))
            )

        return cls(
            neo4j_uri=uri,
            neo4j_username=username,
            neo4j_password=password,
            neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
            neo4j_vector_index=os.getenv("NEO4J_VECTOR_INDEX", "entity_embedding_index"),
            aws_region=aws_region,
            bedrock_embedding_model_id=os.getenv(
                "BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
            ),
        )

