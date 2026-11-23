import hashlib
import json
from pathlib import Path

import numpy as np

from repo_mentor.config import settings
from repo_mentor.chunking.base import Chunk
from repo_mentor.indexing.embedder import Embedder
from repo_mentor.indexing.stores.base import VectorStore

BATCH = 32


class NumpyStore(VectorStore):
    def __init__(self, embedder: Embedder):
        self.embedder = embedder
        self._cache: dict[str, tuple] = {}

    def _base(self, repo_id: str) -> str:
        tag = hashlib.md5(f"{self.embedder.model_name}|{settings.index_version}".encode()).hexdigest()[:8]
        return str(settings.indexes_dir / f"{repo_id}__{tag}")

    def has(self, repo_id: str) -> bool:
        base = self._base(repo_id)
        return Path(base + ".npy").exists() and Path(base + ".json").exists()

    def add(self, repo_id, chunks, on_progress=None):
        vectors = []
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i:i + BATCH]
            vectors.extend(self.embedder.embed([c.text for c in batch]))
            if on_progress:
                on_progress(min(i + BATCH, len(chunks)), len(chunks))

        matrix = np.array(vectors, dtype=np.float32)
        matrix /= np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10

        base = self._base(repo_id)
        # saved only at the end, so an interrupted run is never treated as a finished index
        np.save(base + ".npy", matrix)
        Path(base + ".json").write_text(
            json.dumps({
                "texts": [c.text for c in chunks],
                "metadatas": [c.metadata for c in chunks],
            }),
            encoding="utf-8",
        )
        self._cache.pop(repo_id, None)

    def _load(self, repo_id: str):
        if repo_id not in self._cache:
            base = self._base(repo_id)
            matrix = np.load(base + ".npy")
            data = json.loads(Path(base + ".json").read_text(encoding="utf-8"))
            self._cache[repo_id] = (matrix, data["texts"], data["metadatas"])
        return self._cache[repo_id]

    def search(self, repo_id, query, k):
        matrix, texts, metadatas = self._load(repo_id)
        q = np.array(self.embedder.embed([query], kind="query")[0], dtype=np.float32)
        q /= np.linalg.norm(q) + 1e-10
        scores = matrix @ q                      # cosine similarity
        top = np.argsort(-scores)[:k]
        return [Chunk(text=texts[i], metadata=metadatas[i]) for i in top]