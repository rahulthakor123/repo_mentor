from repo_mentor.config import settings
from repo_mentor.llm.base import LLMProvider


def get_llm() -> LLMProvider:
    name = settings.llm_provider.lower()
    if name == "ollama":
        from repo_mentor.llm.ollama_provider import OllamaProvider
        return OllamaProvider()
    if name == "claude":
        from repo_mentor.llm.claude_provider import ClaudeProvider
        return ClaudeProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {name}")