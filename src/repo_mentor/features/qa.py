from repo_mentor.features.base import Feature, build_context, load_prompt
from repo_mentor.features.registry import register


@register
class QAFeature(Feature):
    name = "qa"
    description = "Answer a question about the repo"

    def _prepare(self, repo_id, question, level):
        chunks = self.retriever.get(repo_id, question)
        system = load_prompt("qa", level)
        user = build_context(chunks, question)
        sources = [c.metadata for c in chunks]
        return system, user, sources

    def run(self, repo_id, user_input, level="beginner"):
        system, user, sources = self._prepare(repo_id, user_input, level)
        return {"answer": self.llm.generate(system, user), "sources": sources}

    def run_stream(self, repo_id, user_input, level="beginner"):
        """Returns (token_generator, sources) so the UI can show text live."""
        system, user, sources = self._prepare(repo_id, user_input, level)
        return self.llm.stream(system, user), sources