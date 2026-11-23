from typing import Iterator
from repo_mentor.config import settings
from repo_mentor.llm.base import LLMProvider


class ClaudeProvider(LLMProvider):
    def __init__(self):
        import anthropic   # imported here so you don't need it installed for Ollama
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def generate(self, system: str, user: str) -> str:
        r = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return r.content[0].text

    def stream(self, system: str, user: str) -> Iterator[str]:
        with self.client.messages.stream(
            model=settings.claude_model,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": user}],
        ) as s:
            yield from s.text_stream