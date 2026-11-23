from repo_mentor.config import settings
from repo_mentor.chunking.base import Chunk
from repo_mentor.indexing.stores.base import VectorStore
from repo_mentor.retrieval.reranker import rerank


class Retriever:
    def __init__(self, store: VectorStore):
        self.store = store

    def get(self, repo_id: str, query: str, k: int | None = None) -> list[Chunk]:
        k = k or settings.top_k
        return rerank(query, self.store.search(repo_id, query, k * 4), k)