from abc import ABC, abstractmethod
from typing import Iterator


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system: str, user: str) -> str: ...

    @abstractmethod
    def stream(self, system: str, user: str) -> Iterator[str]: ...