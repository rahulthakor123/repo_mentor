import re

from repo_mentor.chunking.base import Chunk

PENALTY = 3   # chosen in advance, not tuned
TEST_WORDS = re.compile(r"\b(tests?|testing|pytest|fixtures?|mock)\b", re.I)
DOC_WORDS = re.compile(r"\b(readme|docs?|documentation|guide|tutorial|install(ation)?|set ?up)\b", re.I)


def _kind(path: str) -> str:
    parts = path.lower().split("/")
    name = parts[-1]
    if "tests" in parts[:-1] or "test" in parts[:-1] or name.startswith("test_") or name == "conftest.py":
        return "test"
    if name.endswith((".md", ".rst")) or "docs" in parts[:-1]:
        return "doc"
    return "code"


def rerank(query: str, chunks: list[Chunk], k: int) -> list[Chunk]:
    want_test = bool(TEST_WORDS.search(query))
    want_doc = bool(DOC_WORDS.search(query))
    scored = []
    for rank, c in enumerate(chunks):
        kind = _kind(c.metadata["file_path"])
        penalty = 0
        if (kind == "test" and not want_test) or (kind == "doc" and not want_doc):
            penalty = PENALTY
        scored.append((rank + penalty, rank, c))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [c for _, _, c in scored[:k]]