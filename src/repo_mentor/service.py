from repo_mentor.chunking.code_chunker import CodeChunker
from repo_mentor.config import settings
from repo_mentor.features.architecture_map import ArchitectureMapFeature
from repo_mentor.features.learning_path import LearningPathFeature
from repo_mentor.features.qa import QAFeature
from repo_mentor.features.setup_guide import SetupGuideFeature
from repo_mentor.indexing.embedder import get_embedder
from repo_mentor.indexing.stores.numpy_store import NumpyStore
from repo_mentor.ingestion.architecture import build_architecture
from repo_mentor.ingestion.cloner import clone_repo
from repo_mentor.ingestion.loader import load_repo_files
from repo_mentor.ingestion.overview import build_plan
from repo_mentor.ingestion.setup_facts import build_setup_facts
from repo_mentor.llm.factory import get_llm
from repo_mentor.retrieval.retriever import Retriever
from repo_mentor.features.quiz import QuizFeature

store = NumpyStore(get_embedder())
llm = get_llm()
retriever = Retriever(store)

_plans: dict = {}
_facts: dict = {}
_archs: dict = {}


def _files(repo_id: str):
    return load_repo_files(settings.repos_dir / repo_id)


def get_plan(repo_id: str) -> list:
    if repo_id not in _plans:
        _plans[repo_id] = build_plan(_files(repo_id))
    return _plans[repo_id]


def get_setup_facts(repo_id: str):
    if repo_id not in _facts:
        _facts[repo_id] = build_setup_facts(_files(repo_id))
    return _facts[repo_id]


def get_architecture(repo_id: str) -> dict:
    if repo_id not in _archs:
        _archs[repo_id] = build_architecture(_files(repo_id))
    return _archs[repo_id]


qa = QAFeature(retriever, llm)
learning_path = LearningPathFeature(retriever, llm, get_plan, lambda rid: get_setup_facts(rid).run_cmd)
setup_guide = SetupGuideFeature(retriever, llm, get_setup_facts)
architecture = ArchitectureMapFeature(retriever, llm, get_architecture)
quiz = QuizFeature(retriever, llm, get_architecture)


def index_repo(url: str, on_progress=None) -> str:
    repo_id, path = clone_repo(url)
    if store.has(repo_id):
        return repo_id
    chunker = CodeChunker()
    # code first, docs last, so the cap drops docs before code
    files = sorted(load_repo_files(path), key=lambda f: (f.language == "markdown", f.path))
    chunks = [c for f in files for c in chunker.chunk(f)][: settings.max_chunks]
    store.add(repo_id, chunks, on_progress)
    return repo_id