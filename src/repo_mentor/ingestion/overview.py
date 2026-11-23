import re
from collections import Counter

from repo_mentor.ingestion.loader import SourceFile

CODE_LANGS = {"python", "javascript", "typescript", "java", "go", "rust", "cpp", "c"}
ENTRY_NAMES = {
    "main.py", "app.py", "manage.py", "run.py", "cli.py", "__main__.py",
    "index.js", "server.js", "app.js", "index.ts", "main.go", "main.java",
}
SETUP_PRIORITY = ["requirements.txt", "pyproject.toml", "package.json",
                  "setup.py", "go.mod", "cargo.toml", "pom.xml"]

PY_DEF = re.compile(r"^(?:def|class)\s+(\w+)", re.M)
JS_DEF = re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)", re.M)
FROM_IMPORT = re.compile(r"^\s*from\s+(\.*[\w.]*)\s+import\s+(.+)$", re.M)
PLAIN_IMPORT = re.compile(r"^\s*import\s+([\w.]+)", re.M)


def _top_level_names(f: SourceFile) -> list[str]:
    if f.language == "python":
        return PY_DEF.findall(f.text)
    if f.language in ("javascript", "typescript"):
        return JS_DEF.findall(f.text)
    return []


def _module_index(files: list[SourceFile]) -> dict[str, str]:
    """dotted module name -> file path, e.g. 'app.routers.auth' -> 'app/routers/auth.py'."""
    idx = {}
    for f in files:
        if f.language != "python":
            continue
        mod = f.path[:-3].replace("/", ".")
        if mod.endswith(".__init__"):
            mod = mod[: -len(".__init__")]
        idx[mod] = f.path
    return idx


def _resolve(module: str, idx: dict[str, str]):
    if not module:
        return None
    if module in idx:
        return idx[module]
    for key, path in idx.items():      # src layout: 'src.pkg.mod' imported as 'pkg.mod'
        if key.endswith("." + module):
            return path
    return None


def _import_graph(files: list[SourceFile]) -> dict[str, list[str]]:
    """file path -> repo files it imports, matched on the full module path."""
    idx = _module_index(files)
    graph: dict[str, list[str]] = {}
    for f in files:
        if f.language != "python":
            continue
        pkg = f.path.split("/")[:-1]
        found: list[str] = []

        def add(path):
            if path and path != f.path and not path.endswith("__init__.py") and path not in found:
                found.append(path)

        for m in PLAIN_IMPORT.findall(f.text):
            add(_resolve(m, idx))
        for module, names in FROM_IMPORT.findall(f.text):
            if module.startswith("."):
                up = len(module) - len(module.lstrip("."))
                base = pkg[: max(len(pkg) - (up - 1), 0)]
                rest = module.lstrip(".")
                module = ".".join(base + ([rest] if rest else []))
            add(_resolve(module, idx))
            for n in re.findall(r"\w+", names.split("#")[0]):
                add(_resolve(f"{module}.{n}" if module else n, idx))
        graph[f.path] = found
    return graph


def _reading_order(files: list[SourceFile], imported_by: Counter, limit: int = 8) -> list[str]:
    def depth(p: str) -> int:
        return p.count("/")

    readme = [f.path for f in files if f.path.lower().startswith("readme")]
    setup = [f.path for name in SETUP_PRIORITY for f in files if f.path.lower() == name]
    code = [f for f in files if f.language in CODE_LANGS]
    entry = [f.path for f in code
             if f.path.split("/")[-1] in ENTRY_NAMES and depth(f.path) <= 1]
    rest = sorted(
        (f.path for f in code if f.path not in entry and not f.path.endswith("__init__.py")),
        key=lambda p: ("test" in p.lower(), -imported_by[p], depth(p), p),
    )

    order: list[str] = []
    for p in readme[:1] + setup[:1] + entry + rest:
        if p not in order:
            order.append(p)
    return order[:limit]


def build_plan(files: list[SourceFile], limit: int = 8) -> list[dict]:
    """Structured reading plan: one dict per file, in reading order."""
    by_path = {f.path: f for f in files}
    graph = _import_graph(files)
    imported_by: Counter = Counter()
    for targets in graph.values():
        imported_by.update(targets)
    plan = []
    for p in _reading_order(files, imported_by, limit):
        f = by_path[p]
        plan.append({
            "path": p,
            "language": f.language,
            "lines": len(f.text.splitlines()),
            "names": _top_level_names(f)[:15],
            "uses": graph.get(p, []),
            "imported_by": imported_by[p],
            "head": f.text[:2500],
        })
    return plan