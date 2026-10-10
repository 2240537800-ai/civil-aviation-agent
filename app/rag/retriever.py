"""Hybrid retrieval: BM25 (jieba) + simple embedding cosine (hashing TF)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import jieba
import numpy as np
from rank_bm25 import BM25Okapi

from app import config


@dataclass
class Chunk:
    text: str
    source: str
    idx: int


def _tokenize(text: str) -> List[str]:
    return [t for t in jieba.lcut(text) if t.strip() and not t.isspace()]


def _chunk_text(text: str, size: int, overlap: int) -> List[str]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(text) <= size:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def _hash_embed(tokens: List[str], dim: int = 256) -> np.ndarray:
    vec = np.zeros(dim, dtype=np.float32)
    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


class HybridRetriever:
    def __init__(self, knowledge_dir: Path = None):
        self.knowledge_dir = knowledge_dir or config.KNOWLEDGE_DIR
        self.chunks: List[Chunk] = []
        self._bm25 = None
        self._tokenized: List[List[str]] = []
        self._embeddings: np.ndarray = None
        self.reload()

    def reload(self) -> None:
        self.chunks = []
        paths = sorted(self.knowledge_dir.glob("*.md"))
        for path in paths:
            raw = path.read_text(encoding="utf-8")
            for i, piece in enumerate(
                _chunk_text(raw, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
            ):
                self.chunks.append(Chunk(text=piece, source=path.name, idx=i))

        self._tokenized = [_tokenize(c.text) for c in self.chunks]
        self._bm25 = BM25Okapi(self._tokenized) if self._tokenized else None
        if self.chunks:
            self._embeddings = np.vstack(
                [_hash_embed(toks) for toks in self._tokenized]
            )
        else:
            self._embeddings = np.zeros((0, 256), dtype=np.float32)

    def search(self, query: str, top_k: int = 4) -> List[Tuple[Chunk, float]]:
        if not self.chunks or self._bm25 is None:
            return []

        q_tokens = _tokenize(query)
        bm25_scores = np.array(self._bm25.get_scores(q_tokens), dtype=np.float32)
        if bm25_scores.max() > 0:
            bm25_scores = bm25_scores / (bm25_scores.max() + 1e-8)

        q_vec = _hash_embed(q_tokens)
        dense = self._embeddings @ q_vec
        dense = (dense - dense.min()) / (dense.max() - dense.min() + 1e-8)

        # Hybrid + light "rerank" by length-normalized overlap
        hybrid = 0.55 * bm25_scores + 0.45 * dense
        overlap = np.array(
            [
                len(set(q_tokens) & set(toks)) / (len(set(q_tokens)) + 1e-8)
                for toks in self._tokenized
            ],
            dtype=np.float32,
        )
        final = 0.85 * hybrid + 0.15 * overlap

        idxs = np.argsort(-final)[:top_k]
        return [(self.chunks[i], float(final[i])) for i in idxs if final[i] > 0]

    def format_context(self, hits: List[Tuple[Chunk, float]]) -> str:
        if not hits:
            return "（未检索到相关政策片段）"
        blocks = []
        for rank, (chunk, score) in enumerate(hits, 1):
            blocks.append(
                "[{}] 来源:{} 相关度:{:.3f}\n{}".format(
                    rank, chunk.source, score, chunk.text
                )
            )
        return "\n\n".join(blocks)
