from abc import ABC, abstractmethod
from repo_mentor.chunking.base import Chunk


class VectorStore(ABC):
    @abstractmethod
    def has(self, repo_id: str) -> bool: ...

    @abstractmethod
    def add(self, repo_id: str, chunks: list[Chunk], on_progress=None) -> None: ...

    @abstractmethod
    def search(self, repo_id: str, query: str, k: int) -> list[Chunk]: ...