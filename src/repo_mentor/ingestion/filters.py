from pathlib import Path

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
    "build", ".idea", ".vscode", "target", ".next", "coverage",
}
IGNORE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".pdf", ".zip",
    ".exe", ".dll", ".so", ".pyc", ".lock", ".min.js", ".woff", ".ttf",
    ".mp4", ".mp3", ".sqlite", ".db",
    ".csv", ".tsv", ".ipynb", ".pkl", ".h5", ".npy", ".log", ".map",
}
IGNORE_FILES = {"package-lock.json", "yarn.lock", "poetry.lock", ".gitignore"}
KEEP_TXT = {"requirements.txt", "readme.txt"}


def should_skip(rel_path: Path, abs_path: Path, max_kb: int) -> bool:
    """rel_path is used for name checks, abs_path for reading file size."""
    if any(part in IGNORE_DIRS for part in rel_path.parts):
        return True
    if rel_path.name in IGNORE_FILES or rel_path.suffix.lower() in IGNORE_EXTENSIONS:
        return True
    if rel_path.suffix.lower() == ".txt" and rel_path.name.lower() not in KEEP_TXT:
        return True
    try:
        if abs_path.stat().st_size > max_kb * 1024:
            return True
    except OSError:
        return True    # unreadable file, skip it
    return False