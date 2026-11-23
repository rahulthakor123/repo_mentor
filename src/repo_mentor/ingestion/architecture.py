import re
from collections import Counter

from repo_mentor.ingestion.loader import SourceFile
from repo_mentor.ingestion.overview import _import_graph, _top_level_names

NOISE_DIRS = {"tests", "test", "alembic", "migrations", "versions", "docs", "examples", "venv"}
NOISE_FILES = {"conftest.py", "__init__.py"}
MAX_NODES = 18

ROUTE_FASTAPI = re.compile(r"""^\s*@\w+\.(get|post|put|patch|delete)\(\s*['"]([^'"]*)['"]""")
ROUTE_FLASK = re.compile(r"""^\s*@\w+\.route\(\s*['"]([^'"]*)['"](?:\s*,\s*methods\s*=\s*\[([^\]]*)\])?""")
DEF_LINE = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)")


def _is_noise(path: str) -> bool:
    parts = path.lower().split("/")
    name = parts[-1]
    return (any(p in NOISE_DIRS for p in parts[:-1])
            or name.startswith("test_") or name in NOISE_FILES)


ROUTER_PREFIX = re.compile(r"""APIRouter\([^)]*?prefix\s*=\s*['"]([^'"]*)['"]""")


def find_routes(files: list[SourceFile]) -> list[dict]:
    routes = []
    for f in files:
        if f.language != "python" or _is_noise(f.path):
            continue
        pm = ROUTER_PREFIX.search(f.text)
        prefix = pm.group(1).rstrip("/") if pm else ""
        lines = f.text.splitlines()
        for i, line in enumerate(lines):
            found = None
            m = ROUTE_FASTAPI.match(line)
            if m:
                found = (m.group(1).upper(), m.group(2))
            else:
                m = ROUTE_FLASK.match(line)
                if m:
                    methods = re.findall(r"[A-Za-z]+", m.group(2) or "") or ["get"]
                    found = (",".join(x.upper() for x in methods), m.group(1))
            if not found:
                continue
            for nxt in lines[i + 1:i + 6]:      # skip stacked decorators
                d = DEF_LINE.match(nxt)
                if d:
                    routes.append({"method": found[0],
                                   "path": (prefix + found[1]) or "(router root)",
                                   "func": d.group(1), "file": f.path})
                    break
    return routes


def build_architecture(files: list[SourceFile]) -> dict:
    by_path = {f.path: f for f in files}
    graph = _import_graph(files)
    py = [f.path for f in files if f.language == "python" and not _is_noise(f.path)]
    allowed = set(py)
    out = {p: [t for t in graph.get(p, []) if t in allowed] for p in py}
    imported_by: Counter = Counter()
    for targets in out.values():
        imported_by.update(targets)

    defs: dict[str, list[str]] = {}
    for p in py:
        for name in _top_level_names(by_path[p]):
            defs.setdefault(name, []).append(p)

    ranked = sorted(py, key=lambda p: (-(imported_by[p] + len(out[p])), p))
    chosen = sorted(ranked[:MAX_NODES])
    keep = set(chosen)
    return {
        "nodes": [{"path": p,
                   "names": _top_level_names(by_path[p])[:12],
                   "imported_by": imported_by[p],
                   "head": by_path[p].text[:1500]} for p in chosen],
        "edges": [(s, t) for s in chosen for t in out[s] if t in keep],
        "routes": find_routes(files),
        "total": len(py),
        "defs": defs,
        "imported_by": dict(imported_by),
    }


def _reduce(nodes: list[str], edges: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Hide an arrow A->C when A already reaches C through another file (A->B->C)."""
    out: dict[str, set[str]] = {n: set() for n in nodes}
    for s, t in edges:
        out[s].add(t)

    def reaches(start, goal, skip_edge):
        seen, stack = set(), [start]
        while stack:
            cur = stack.pop()
            for nxt in out[cur]:
                if (cur, nxt) == skip_edge or nxt in seen:
                    continue
                if nxt == goal:
                    return True
                seen.add(nxt)
                stack.append(nxt)
        return False

    kept = []
    for s, t in edges:
        in_cycle = reaches(t, s, None)          # never hide an arrow that is part of a cycle
        if not in_cycle and reaches(s, t, (s, t)):
            continue
        kept.append((s, t))
    return kept


def visible_edges(arch: dict) -> list[tuple[str, str]]:
    return _reduce([n["path"] for n in arch["nodes"]], arch["edges"])


def _label(path: str) -> str:
    return "/".join(path.split("/")[-2:])      # 'app/routers/auth.py' -> 'routers/auth.py'


def to_mermaid(arch: dict) -> str:
    ids = {n["path"]: f"n{i}" for i, n in enumerate(arch["nodes"])}
    lines = ["flowchart TD"]
    for n in arch["nodes"]:
        lines.append(f'  {ids[n["path"]]}["{_label(n["path"])}"]')
    for s, t in visible_edges(arch):
        lines.append(f"  {ids[s]} --> {ids[t]}")
    return "\n".join(lines)