from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    # which provider to use: "ollama" or "claude"
    llm_provider: str = "ollama"
    embedding_provider: str = "ollama"

    # Ollama
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_llm_model: str = "llama3.2"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_num_ctx: int = 8192

    # Claude (used only later)
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5-5"

    repos_dir: Path = ROOT / "data" / "repos"
    indexes_dir: Path = ROOT / "data" / "indexes"
    index_version: str = "code-v3-prefix"   # change this when chunking or embedding changes
    max_file_size_kb: int = 100
    chunk_lines: int = 60
    chunk_overlap: int = 10
    max_chunks: int = 1500
    top_k: int = 5


settings = Settings()
settings.repos_dir.mkdir(parents=True, exist_ok=True)
settings.indexes_dir.mkdir(parents=True, exist_ok=True)