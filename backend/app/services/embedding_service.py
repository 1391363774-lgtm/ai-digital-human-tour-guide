from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingResult:
    text: str
    vector: list[float]
    provider: str
    dimension: int


class EmbeddingService:
    """Embedding 抽象。

    MVP 默认使用确定性本地向量，保证无 API Key、无模型权重时也能跑通入库与检索链路。
    后续接入 BGE-M3 时，只需要替换 `embed_texts` 的实现或新增 provider。
    """

    def __init__(self, provider: str = "local_hash", dimension: int = 384) -> None:
        self.provider = provider
        self.dimension = dimension

    def embed_texts(self, texts: list[str]) -> list[EmbeddingResult]:
        return [
            EmbeddingResult(
                text=text,
                vector=build_hash_embedding(text, self.dimension),
                provider=self.provider,
                dimension=self.dimension,
            )
            for text in texts
        ]

    def embed_query(self, query: str) -> EmbeddingResult:
        return self.embed_texts([query])[0]


def build_hash_embedding(text: str, dimension: int) -> list[float]:
    vector = [0.0] * dimension
    tokens = tokenize(text)
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = 1.0 + min(len(token), 8) / 10
        vector[index] += sign * weight

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def tokenize(text: str) -> list[str]:
    chinese_terms = re.findall(r"[\u4e00-\u9fff]{1,2}", text)
    latin_terms = re.findall(r"[A-Za-z0-9_]+", text.lower())
    return chinese_terms + latin_terms
