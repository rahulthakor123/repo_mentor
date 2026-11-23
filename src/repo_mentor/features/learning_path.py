from repo_mentor.features.base import Feature, load_prompt
from repo_mentor.features.registry import register
from repo_mentor.ingestion.setup_facts import parse_requirements

ENTRY_NAMES = {"main.py", "app.py", "manage.py", "run.py", "cli.py"}


@register
class LearningPathFeature(Feature):
    name = "learning_path"
    description = "Create a step-by-step reading path for a beginner"

    def __init__(self, retriever, llm, plan_fn, run_cmd_fn=None):
        super().__init__(retriever, llm)
        self.plan_fn = plan_fn
        self.run_cmd_fn = run_cmd_fn

    @staticmethod
    def _facts(step) -> str:
        parts = [f"{step['lines']} lines"]
        if step["names"]:
            parts.append("defines: " + ", ".join(f"`{n}`" for n in step["names"]))
        if step["uses"]:
            parts.append("uses: " + ", ".join(f"`{u}`" for u in step["uses"]))
        if step["imported_by"]:
            parts.append(f"used by {step['imported_by']} other file(s)")
        return " · ".join(parts)

    def _explain(self, step, i, total, level):
        if step["path"].lower() == "requirements.txt":
            pkgs = parse_requirements(step["head"])
            yield "- **Why read it now:** It lists every library you must install before the project can run.\n"
            yield "- **What to look for:** The libraries it needs: " + ", ".join(f"`{p}`" for p in pkgs) + "."
            return
        system = load_prompt("learning_step", level)
        user = (
            f"File: {step['path']} (step {i} of {total} in the reading order)\n"
            f"Facts: {self._facts(step)}\n\n"
            f"FILE CONTENT (first part):\n{step['head']}"
        )
        yield from self.llm.stream(system, user)


    def _exercise(self, plan, run_cmd) -> str:
        lines = ["### First exercise"]
        n = 1
        if any(s["path"].lower() == "requirements.txt" for s in plan):
            lines.append(f"{n}. Install the dependencies: `python -m pip install -r requirements.txt`")
            n += 1
        entry = next((s for s in plan if s["path"].split("/")[-1] in ENTRY_NAMES), None)
        if run_cmd:
            lines.append(f"{n}. Run the project: `{run_cmd}`")
            n += 1
        if entry:
            target = entry["uses"][0] if entry["lines"] < 10 and entry["uses"] else entry["path"]
            lines.append(f"{n}. Change one small value in `{target}` and run it again to see what changes.")
        elif plan:
            lines.append(f"{n}. Open `{plan[0]['path']}`, change one small value, then run the project again.")
        return "\n".join(lines)

    def _generate(self, repo_id, level):
        plan = self.plan_fn(repo_id)
        if not plan:
            yield "I couldn't find readable source files in this repo."
            return
        yield f"**Reading path: {len(plan)} files, in this order.**\n\n"
        for i, step in enumerate(plan, 1):
            yield f"### Step {i}: `{step['path']}`\n_{self._facts(step)}_\n\n"
            yield from self._explain(step, i, len(plan), level)
            yield "\n\n"
        run_cmd = self.run_cmd_fn(repo_id) if self.run_cmd_fn else ""
        yield self._exercise(plan, run_cmd)

    def run(self, repo_id, user_input="", level="beginner"):
        return {"answer": "".join(self._generate(repo_id, level)), "sources": []}

    def run_stream(self, repo_id, user_input="", level="beginner"):
        return self._generate(repo_id, level), []