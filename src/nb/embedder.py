"""Calcolo degli embedding: fastembed (ONNX, CPU) o finto per i test."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Protocol

import numpy as np

from nb.config import Config

CACHE_MODELLI = Path.home() / ".cache" / "nb" / "fastembed"


class Embedder(Protocol):
    model_id: str
    dim: int

    def embed(self, testi: list[str]) -> np.ndarray: ...

    def embed_query(self, testo: str) -> np.ndarray: ...


def _normalizza(m: np.ndarray) -> np.ndarray:
    norme = np.linalg.norm(m, axis=1, keepdims=True)
    norme[norme == 0] = 1
    return (m / norme).astype(np.float32)


class FastEmbedder:
    def __init__(self, model_id: str, dim: int):
        self.model_id = model_id
        self.dim = dim
        self._modello = None

    def _m(self):
        if self._modello is None:
            from fastembed import TextEmbedding

            self._modello = TextEmbedding(model_name=self.model_id, cache_dir=str(CACHE_MODELLI))
        return self._modello

    def embed(self, testi: list[str]) -> np.ndarray:
        if not testi:
            return np.zeros((0, self.dim), np.float32)
        return _normalizza(np.array(list(self._m().embed(testi, batch_size=64)), dtype=np.float32))

    def embed_query(self, testo: str) -> np.ndarray:
        return self.embed([testo])[0]


class FakeEmbedder:
    """Deterministico e senza download: bag-of-words con hashing. Solo per i test."""

    def __init__(self, model_id: str = "fake", dim: int = 384):
        self.model_id = model_id
        self.dim = dim

    def embed(self, testi: list[str]) -> np.ndarray:
        m = np.zeros((len(testi), self.dim), np.float32)
        for i, t in enumerate(testi):
            for parola in re.findall(r"\w+", t.lower()):
                h = int.from_bytes(hashlib.blake2b(parola.encode(), digest_size=4).digest(), "little")
                m[i, h % self.dim] += 1.0
        return _normalizza(m)

    def embed_query(self, testo: str) -> np.ndarray:
        return self.embed([testo])[0]


def crea(config: Config) -> Embedder:
    if os.environ.get("NB_EMBEDDER") == "fake":
        return FakeEmbedder(config.model_id, config.dim)
    return FastEmbedder(config.model_id, config.dim)
