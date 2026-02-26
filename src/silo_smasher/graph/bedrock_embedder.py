from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class BedrockEmbedder:
    def __init__(self, region_name: str, model_id: str):
        self._client = boto3.client("bedrock-runtime", region_name=region_name)
        self._model_id = model_id

    def embed_text(self, text: str) -> list[float]:
        try:
            response = self._client.invoke_model(
                modelId=self._model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"inputText": text}),
            )
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Bedrock embedding request failed: {exc}") from exc

        raw_body = response.get("body")
        if raw_body is None:
            raise RuntimeError("Bedrock response body is empty.")

        payload = json.loads(raw_body.read())
        if "embedding" in payload and isinstance(payload["embedding"], list):
            return [float(value) for value in payload["embedding"]]

        by_type = payload.get("embeddingsByType")
        if isinstance(by_type, dict):
            for value in by_type.values():
                if isinstance(value, list):
                    return [float(item) for item in value]

        raise RuntimeError(f"Unexpected Bedrock embedding payload: {payload}")

    @staticmethod
    def dimensions(embedding: list[float]) -> int:
        if not embedding:
            raise RuntimeError("Embedding is empty.")
        return len(embedding)

    @staticmethod
    def serialize_embedding(values: list[float]) -> list[float]:
        return [float(v) for v in values]

