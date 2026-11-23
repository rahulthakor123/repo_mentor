import re
from pathlib import Path
from git import Repo
from repo_mentor.config import settings


def repo_id_from_url(url: str) -> str:
    m = re.search(r"github\.com[/:]([^/]+)/([^/.]+)", url)
    if not m:
        raise ValueError("Please give a valid GitHub repo URL")
    return f"{m.group(1)}__{m.group(2)}"


def clone_repo(url: str) -> tuple[str, Path]:
    repo_id = repo_id_from_url(url)
    dest = settings.repos_dir / repo_id
    if dest.exists():          # already cloned, reuse it
        return repo_id, dest
    Repo.clone_from(url, dest, depth=1)   # depth=1 = fast, latest code only
    return repo_id, dest