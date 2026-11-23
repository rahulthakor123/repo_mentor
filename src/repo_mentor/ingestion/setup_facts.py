import json
import re
from dataclasses import dataclass, field

from repo_mentor.ingestion.loader import SourceFile

ENTRY_PRIORITY = ["main.py", "app.py", "run.py", "manage.py", "cli.py", "__main__.py"]
ENV_EXAMPLE_FILES = {".env.example", ".env.sample", "env.example", ".env.template"}
IGNORE_ENV = {"PATH", "HOME", "USER", "USERNAME", "PWD", "TEMP", "TMP"}

REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9_.\-]*)")
ENV_LINE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=", re.M)
ENV_PY = re.compile(
    r"""os\.(?:getenv|environ\.get)\(\s*['"](\w+)['"]|os\.environ\[\s*['"](\w+)['"]\s*\]"""
)


@dataclass
class SetupFacts:
    language: str = "unknown"          # python / node / unknown
    python_hint: str = ""
    packages: list = field(default_factory=list)
    pinned: bool = False
    install_cmd: str = ""
    entry: str = ""
    run_cmd: str = ""
    env_vars: list = field(default_factory=list)
    has_env_example: bool = False
    has_readme: bool = False
    notes: list = field(default_factory=list)


def parse_requirements(text: str) -> list[str]:
    pkgs = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "http", "git+")):
            continue
        m = REQ_NAME.match(line)
        if m:
            pkgs.append(m.group(1))
    return pkgs


def _pyproject_deps(text: str) -> list[str]:
    m = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text, re.S | re.M)
    if not m:
        return []
    out = []
    for item in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
        n = REQ_NAME.match(item)
        if n:
            out.append(n.group(1))
    return out


def _find_entry(files: list[SourceFile]):
    py = [f for f in files if f.language == "python"]
    for name in ENTRY_PRIORITY:
        for depth in (0, 1):
            for f in py:
                if f.path.count("/") == depth and f.path.split("/")[-1] == name:
                    return f
    return None


def _python_run(path: str, text: str, packages: list[str]) -> str:
    low = text.lower()
    pk = {p.lower() for p in packages}
    module = path[:-3].replace("/", ".")
    if "streamlit" in low:
        return f"python -m streamlit run {path}"
    if "uvicorn.run(" in low:
        return f"python {path}"
    if "fastapi(" in low or ("fastapi" in pk and re.search(r"\bapp\b", text)):
        return f"python -m uvicorn {module}:app --reload"
    if "flask(" in low and "app.run(" not in low:
        return f"python -m flask --app {path} run"
    return f"python {path}"


def _env_vars(files: list[SourceFile]) -> list[str]:
    found: set[str] = set()
    for f in files:
        base = f.path.split("/")[-1].lower()
        if base in ENV_EXAMPLE_FILES:
            found.update(ENV_LINE.findall(f.text))
        elif f.language == "python":
            for a, b in ENV_PY.findall(f.text):
                found.add(a or b)
    return sorted(found - IGNORE_ENV)[:15]


def build_setup_facts(files: list[SourceFile]) -> SetupFacts:
    by = {f.path.lower(): f for f in files}
    facts = SetupFacts()
    facts.has_readme = any("/" not in p and p.startswith("readme") for p in by)
    if not facts.has_readme:
        facts.notes.append("This repo has no README, so these steps were worked out from the code only.")
    facts.env_vars = _env_vars(files)
    facts.has_env_example = any(p in ENV_EXAMPLE_FILES for p in by)

    req, pyp, setup_py = by.get("requirements.txt"), by.get("pyproject.toml"), by.get("setup.py")
    pkg_json = by.get("package.json")

    if req or pyp or setup_py:
        facts.language = "python"
        if req:
            facts.packages = parse_requirements(req.text)
            facts.install_cmd = "python -m pip install -r requirements.txt"
            facts.pinned = any("==" in ln for ln in req.text.splitlines())
            if not facts.pinned and facts.packages:
                facts.notes.append(
                    "`requirements.txt` has no pinned versions, so pip installs the newest releases. "
                    "If something breaks, a newer library version may be the cause."
                )
        else:
            facts.packages = _pyproject_deps(pyp.text) if pyp else []
            facts.install_cmd = "python -m pip install -e ."

        for name in ("runtime.txt", ".python-version"):
            if name in by and by[name].text.strip():
                facts.python_hint = by[name].text.strip().splitlines()[0]
                break
        if not facts.python_hint and pyp:
            m = re.search(r"requires-python\s*=\s*[\"']([^\"']+)[\"']", pyp.text)
            if m:
                facts.python_hint = m.group(1)

        entry = _find_entry(files)
        if entry:
            facts.entry = entry.path
            facts.run_cmd = _python_run(entry.path, entry.text, facts.packages)
            if "uvicorn" in facts.run_cmd:
                facts.notes.append("The run command assumes your FastAPI object is named `app`.")
        else:
            facts.notes.append(
                "I couldn't find an obvious entry point (main.py, app.py, ...). "
                "Check the learning path to see which file to run."
            )

    elif pkg_json:
        facts.language = "node"
        try:
            data = json.loads(pkg_json.text)
        except json.JSONDecodeError:
            data = {}
        facts.packages = sorted(data.get("dependencies", {}))[:30]
        facts.install_cmd = "npm install"
        scripts = data.get("scripts", {})
        if "start" in scripts:
            facts.run_cmd = "npm start"
        elif "dev" in scripts:
            facts.run_cmd = "npm run dev"
        else:
            facts.notes.append("`package.json` has no `start` or `dev` script, so check the README to run it.")

    else:
        facts.notes.append("I couldn't find `requirements.txt`, `pyproject.toml` or `package.json`.")

    return facts