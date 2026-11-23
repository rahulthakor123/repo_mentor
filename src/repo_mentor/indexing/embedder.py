from abc import ABC, abstractmethod
from repo_mentor.config import settings


class Embedder(ABC):
    model_name: str

    @abstractmethod
    def embed(self, texts: list[str], kind: str = "document") -> list[list[float]]: ...


class OllamaEmbedder(Embedder):
    def __init__(self):
        import ollama
        self.client = ollama.Client(host=settings.ollama_host, timeout=120)
        self.model_name = settings.ollama_embedding_model

    def embed(self, texts, kind="document"):
        prefix = "search_query: " if kind == "query" else "search_document: "
        texts = [prefix + t for t in texts]
        return self.client.embed(model=self.model_name, input=texts)["embeddings"]


def get_embedder() -> Embedder:
    name = settings.embedding_provider.lower()
    if name == "ollama":
        return OllamaEmbedder()
    # later: add OpenAIEmbedder / VoyageEmbedder here
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {name}")