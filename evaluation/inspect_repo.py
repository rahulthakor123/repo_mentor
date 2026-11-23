import ast
import sys

from repo_mentor.config import settings
from repo_mentor.ingestion.loader import load_repo_files

repo_id = sys.argv[1]
files = load_repo_files(settings.repos_dir / repo_id)
print(f"{len(files)} files\n")
for f in sorted(files, key=lambda x: x.path):
    n = len(f.text.splitlines())
    print(f"{f.path}  ({f.language}, {n} lines)")
    if f.language != "python":
        if "--heads" in sys.argv:
            for ln in [l for l in f.text.splitlines() if l.strip()][:6]:
                print("   | " + ln[:90])
        continue
    try:
        tree = ast.parse(f.text)
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            decos = " ".join("@" + ast.unparse(d) for d in node.decorator_list)
            print(f"   L{node.lineno} {type(node).__name__[:5]} {node.name} {decos}".rstrip())