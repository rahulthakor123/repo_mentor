from dataclasses import dataclass
from pathlib import Path
from repo_mentor.config import settings
from repo_mentor.ingestion.filters import should_skip

LANGUAGES = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".java": "java", ".go": "go", ".rs": "rust", ".cpp": "cpp",
    ".c": "c", ".md": "markdown", ".json": "json", ".yml": "yaml",
    ".yaml": "yaml", ".toml": "toml", ".txt": "text", ".html": "html",
    ".css": "css",
}


@dataclass
class SourceFile:
    path: str        # relative path, like "src/app.py" (used for citations)
    language: str
    text: str


def load_repo_files(repo_dir: Path) -> list[SourceFile]:
    files = []
    for p in repo_dir.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(repo_dir)
        if should_skip(rel, p, settings.max_file_size_kb):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue   # binary or unreadable file
        if not text.strip():
            continue
        files.append(SourceFile(rel.as_posix(), LANGUAGES.get(p.suffix.lower(), "text"), text))
    return files