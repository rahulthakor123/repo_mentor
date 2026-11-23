from abc import ABC, abstractmethod
from pathlib import Path
from repo_mentor.chunking.base import Chunk

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def load_prompt(name: str, level: str = "beginner") -> str:
    base = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    style_file = PROMPTS_DIR / f"{level}_style.md"
    style = style_file.read_text(encoding="utf-8") if style_file.exists() else ""
    return f"{base}\n\n{style}".strip()


def build_context(chunks: list[Chunk], question: str) -> str:
    parts = []
    for c in chunks:
        m = c.metadata
        parts.append(f"[{m['file_path']} lines {m['start_line']}-{m['end_line']}]\n{c.text}")
    return "CODE CONTEXT:\n\n" + "\n\n---\n\n".join(parts) + f"\n\nQUESTION: {question}"


class Feature(ABC):
    name: str
    description: str

    def __init__(self, retriever, llm):
        self.retriever = retriever
        self.llm = llm

    @abstractmethod
    def run(self, repo_id: str, user_input: str, level: str = "beginner") -> dict: ...