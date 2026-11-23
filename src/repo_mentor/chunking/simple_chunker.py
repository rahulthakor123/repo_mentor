from repo_mentor.config import settings
from repo_mentor.chunking.base import Chunk, Chunker
from repo_mentor.ingestion.loader import SourceFile


class SimpleChunker(Chunker):
    def chunk(self, file: SourceFile) -> list[Chunk]:
        lines = file.text.splitlines()
        size, overlap = settings.chunk_lines, settings.chunk_overlap
        step = size - overlap
        chunks = []
        for start in range(0, len(lines), step):
            part = lines[start:start + size]
            if not "".join(part).strip():
                continue
            chunks.append(Chunk(
                text=f"# File: {file.path}\n" + "\n".join(part),
                metadata={
                    "file_path": file.path,
                    "language": file.language,
                    "start_line": start + 1,
                    "end_line": start + len(part),
                },
            ))
            if start + size >= len(lines):
                break
        return chunks