from typing import Iterator
import ollama
from repo_mentor.config import settings
from repo_mentor.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self):
        self.client = ollama.Client(host=settings.ollama_host, timeout=300)
        self.options = {"num_ctx": settings.ollama_num_ctx, "temperature": 0.2}

    def _messages(self, system, user):
        return [{"role": "system", "content": system},
                {"role": "user", "content": user}]

    def generate(self, system: str, user: str) -> str:
        r = self.client.chat(model=settings.ollama_llm_model,
                             messages=self._messages(system, user),
                             options=self.options)
        return r["message"]["content"]

    def stream(self, system: str, user: str) -> Iterator[str]:
        for part in self.client.chat(model=settings.ollama_llm_model,
                                     messages=self._messages(system, user),
                                     options=self.options,
                                     stream=True):
            yield part["message"]["content"]