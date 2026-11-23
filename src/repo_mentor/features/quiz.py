import random
import re
from collections import Counter

from repo_mentor.features.base import Feature
from repo_mentor.features.registry import register


def _options(rng, correct, pool, n=4):
    wrong = [p for p in dict.fromkeys(pool) if p != correct]
    if len(wrong) < n - 1:
        return None
    rng.shuffle(wrong)
    opts = [correct] + wrong[: n - 1]
    rng.shuffle(opts)
    return opts


def _q_defines(rng, arch, nodes):
    nodeset = set(nodes)
    cands = sorted((name, paths[0]) for name, paths in arch["defs"].items()
                   if len(paths) == 1 and paths[0] in nodeset and not name.startswith("_"))
    if not cands:
        return None
    name, path = rng.choice(cands)
    opts = _options(rng, path, nodes)
    if not opts:
        return None
    return {"q": f"Which file defines `{name}`?", "options": opts, "answer": path,
            "why": f"`{name}` is defined in `{path}`."}


def _q_route(rng, arch, nodes):
    routes = arch["routes"]
    counts = Counter(r["func"] for r in routes)
    cands = [r for r in routes if counts[r["func"]] == 1]
    if not cands:
        return None
    r = rng.choice(cands)
    answer = f"{r['method']} {r['path']}"
    opts = _options(rng, answer, [f"{x['method']} {x['path']}" for x in routes])
    if not opts:
        return None
    return {"q": f"Which route is handled by the function `{r['func']}` in `{r['file']}`?",
            "options": opts, "answer": answer,
            "why": f"`{r['func']}` handles `{answer}`."}


def _q_imports(rng, arch, nodes):
    importers: dict[str, list[str]] = {}
    for s, t in arch["edges"]:
        importers.setdefault(t, []).append(s)
    cands = [t for t, srcs in importers.items()
             if len([n for n in nodes if n != t and n not in srcs]) >= 3]
    if not cands:
        return None
    t = rng.choice(sorted(cands))
    s = rng.choice(sorted(importers[t]))
    others = [n for n in nodes if n != t and n not in importers[t]]
    opts = _options(rng, s, others + [s])
    if not opts:
        return None
    return {"q": f"Which of these files imports `{t}`?", "options": opts, "answer": s,
            "why": f"`{s}` imports `{t}`."}


def _q_hub(rng, arch, nodes):
    counts = arch["imported_by"]
    if not counts:
        return None
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top, n = ranked[0]
    if top not in nodes or (len(ranked) > 1 and ranked[1][1] == n):
        return None                      # skip if there is a tie
    opts = _options(rng, top, nodes)
    if not opts:
        return None
    return {"q": "Which source file is imported by the most other source files?",
            "options": opts, "answer": top,
            "why": f"`{top}` is imported by {n} other files (tests and migrations are not counted)."}


@register
class QuizFeature(Feature):
    name = "quiz"
    description = "Multiple-choice quiz built from the real code"

    def __init__(self, retriever, llm, arch_fn):
        super().__init__(retriever, llm)
        self.arch_fn = arch_fn

    def generate(self, repo_id: str, seed: str, count: int = 5) -> list[dict]:
        arch = self.arch_fn(repo_id)
        nodes = [n["path"] for n in arch["nodes"]]
        if len(nodes) < 4:
            return []
        rng = random.Random(seed)
        makers = [_q_defines, _q_route, _q_imports, _q_hub]
        quiz, seen, used = [], set(), set()
        for maker in makers * 4:
            if len(quiz) >= count:
                break
            q = maker(rng, arch, nodes)
            if not q or q["q"] in seen:
                continue
            names = set(re.findall(r"`([^`]+)`", q["q"]))
            if names & used:
                continue                     # don't ask twice about the same name
            seen.add(q["q"])
            used |= names
            quiz.append(q)
        return quiz

    def run(self, repo_id, user_input="", level="beginner"):
        return {"quiz": self.generate(repo_id, user_input or repo_id), "sources": []}