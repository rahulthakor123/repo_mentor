from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from repo_mentor.ingestion.loader import SourceFile


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)  # file_path, language, start_line, end_line


class Chunker(ABC):
    @abstractmethod
    def chunk(self, file: SourceFile) -> list[Chunk]: ...