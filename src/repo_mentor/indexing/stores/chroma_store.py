import hashlib
import chromadb
from repo_mentor.config import settings
from repo_mentor.chunking.base import Chunk
from repo_mentor.indexing.embedder import Embedder
from repo_mentor.indexing.stores.base import VectorStore

BATCH = 32


class ChromaStore(VectorStore):
    def __init__(self, embedder: Embedder):
        self.embedder = embedder
        self.client = chromadb.PersistentClient(path=str(settings.indexes_dir))

    def _name(self, repo_id: str) -> str:
        tag = hashlib.md5(self.embedder.model_name.encode()).hexdigest()[:8]
        return f"{repo_id[:45]}__{tag}"     # Chroma names must be <= 63 chars

    def _collection(self, repo_id: str):
        return self.client.get_or_create_collection(
            self._name(repo_id), metadata={"hnsw:space": "cosine"}
        )

    def has(self, repo_id: str) -> bool:
        try:
            return self.client.get_collection(self._name(repo_id)).count() > 0
        except Exception:
            return False

    def add(self, repo_id, chunks, on_progress=None):
        col = self._collection(repo_id)
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i:i + BATCH]
            col.add(
                ids=[f"{i + j}" for j in range(len(batch))],
                documents=[c.text for c in batch],
                embeddings=self.embedder.embed([c.text for c in batch]),
                metadatas=[c.metadata for c in batch],
            )
            if on_progress:
                on_progress(min(i + BATCH, len(chunks)), len(chunks))

    def search(self, repo_id, query, k):
        res = self._collection(repo_id).query(
            query_embeddings=self.embedder.embed([query]), n_results=k
        )
        return [Chunk(text=d, metadata=m)
                for d, m in zip(res["documents"][0], res["metadatas"][0])]