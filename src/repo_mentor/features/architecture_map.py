import re

from repo_mentor.features.base import Feature, load_prompt
from repo_mentor.features.registry import register
from repo_mentor.ingestion.architecture import to_mermaid, visible_edges

MAX_ROUTES = 30


@register
class ArchitectureMapFeature(Feature):
    name = "architecture_map"
    description = "Diagram of how the files depend on each other"

    def __init__(self, retriever, llm, arch_fn):
        super().__init__(retriever, llm)
        self.arch_fn = arch_fn
        self._cache: dict = {}

    def _role(self, node, level) -> str:
        names = ", ".join(node["names"]) or "none"
        user = (f"File: {node['path']}\nNames in the file: {names}\n\n"
                f"FILE CONTENT (first part):\n{node['head']}")
        text = self.llm.generate(load_prompt("architecture_role", level), user)
        first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        first = first.lstrip("-*• ").strip()
        first = re.sub(r"^(defines?|describes?)\s*:\s*", "", first, flags=re.I)
        if first and set(re.findall(r"\w+", first)) <= set(node["names"]):
            first = ""        # the model only repeated the names
        return first[:240] or "(no description from the model)"

    def _build(self, repo_id, level):
        arch = self.arch_fn(repo_id)
        if not arch["nodes"]:
            yield "I couldn't find Python source files to map. This feature only reads Python imports for now."
            return

        shown = len(visible_edges(arch))
        yield ("**How the files connect.** An arrow `A --> B` means A imports B. "
               f"To keep the picture readable, {shown} of {len(arch['edges'])} import links are drawn: "
               "a link is hidden when A already reaches B through another file.\n\n")
        yield f"```mermaid\n{to_mermaid(arch)}\n```\n\n"
        if arch["total"] > len(arch["nodes"]):
            yield (f"_Showing the {len(arch['nodes'])} most connected of {arch['total']} source files. "
                   "Tests and migrations are left out._\n\n")

        routes = arch["routes"]
        if routes:
            yield "### Endpoints\n\n| Method | Path | Function | File |\n|---|---|---|---|\n"
            for r in routes[:MAX_ROUTES]:
                yield f"| {r['method']} | `{r['path']}` | `{r['func']}` | `{r['file']}` |\n"
            if len(routes) > MAX_ROUTES:
                yield f"\n_...and {len(routes) - MAX_ROUTES} more._\n"
            yield "\n_Paths are as written in the decorator. A router prefix may be added in front._\n\n"

        yield "### What each file does\n\n"
        for n in arch["nodes"]:
            facts = []
            if n["names"]:
                facts.append("defines " + ", ".join(f"`{x}`" for x in n["names"][:6]))
            if n["imported_by"]:
                facts.append(f"used by {n['imported_by']} file(s)")
            suffix = f" _({'; '.join(facts)})_" if facts else ""
            yield f"- `{n['path']}`: {self._role(n, level)}{suffix}\n"

    def _generate(self, repo_id, level):
        key = (repo_id, level)
        if key in self._cache:
            yield self._cache[key]
            return
        parts = []
        for chunk in self._build(repo_id, level):
            parts.append(chunk)
            yield chunk
        self._cache[key] = "".join(parts)

    def run(self, repo_id, user_input="", level="beginner"):
        return {"answer": "".join(self._generate(repo_id, level)), "sources": []}

    def run_stream(self, repo_id, user_input="", level="beginner"):
        return self._generate(repo_id, level), []