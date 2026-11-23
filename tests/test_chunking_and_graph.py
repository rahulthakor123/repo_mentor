from repo_mentor.chunking.base import Chunk
from repo_mentor.chunking.code_chunker import CodeChunker
from repo_mentor.features.quiz import QuizFeature
from repo_mentor.ingestion.architecture import _reduce, build_architecture
from repo_mentor.ingestion.loader import SourceFile
from repo_mentor.ingestion.overview import _import_graph
from repo_mentor.retrieval.reranker import rerank


def _headers(chunks):
    return [c.text.splitlines()[0].split("| ", 1)[1] for c in chunks]


def test_one_chunk_per_function():
    text = "import os\n\ndef foo():\n    return 1\n\ndef bar():\n    return 2\n"
    chunks = CodeChunker().chunk(SourceFile("a.py", "python", text))
    assert _headers(chunks) == ["script", "function foo", "function bar"]
    foo = chunks[1]
    assert (foo.metadata["start_line"], foo.metadata["end_line"]) == (3, 4)


def test_long_class_is_split_into_methods():
    src = "class A:\n" + "".join(f"    def m{i}(self):\n        return {i}\n\n" for i in range(12))
    headers = _headers(CodeChunker().chunk(SourceFile("a.py", "python", src)))
    assert "function A.m0" in headers and "function A.m11" in headers


def test_fallbacks_do_not_crash():
    assert CodeChunker().chunk(SourceFile("a.py", "python", "def (:\n"))               # syntax error
    assert CodeChunker().chunk(SourceFile("README.md", "markdown", "# Title\n\ntext\n"))


def _repo():
    return [
        SourceFile("app/__init__.py", "python", "# package\n"),
        SourceFile("app/routers/__init__.py", "python", "# package\n"),
        SourceFile("app/main.py", "python",
                   "from app.routers import items\nfrom app.config import settings\n\ndef create_app():\n    pass\n"),
        SourceFile("app/config.py", "python", "settings = 1\n\ndef get_settings():\n    pass\n"),
        SourceFile("app/database.py", "python", "from app import config\n\ndef get_db():\n    pass\n"),
        SourceFile("app/routers/items.py", "python",
                   "from app.database import get_db\nfrom ..config import settings\n\ndef list_items():\n    pass\n"),
        SourceFile("README.md", "markdown", "from app.config import x\n"),
    ]


def test_import_graph():
    g = _import_graph(_repo())
    assert set(g["app/main.py"]) == {"app/routers/items.py", "app/config.py"}
    assert set(g["app/routers/items.py"]) == {"app/database.py", "app/config.py"}
    assert g["app/database.py"] == ["app/config.py"]       # 'from app import config'
    assert "README.md" not in g                            # imports inside Markdown are ignored


def test_edge_reduction():
    nodes = ["a", "b", "c"]
    assert _reduce(nodes, [("a", "b"), ("b", "c"), ("a", "c")]) == [("a", "b"), ("b", "c")]
    assert _reduce(["a", "b"], [("a", "b"), ("b", "a")]) == [("a", "b"), ("b", "a")]   # cycles stay


def test_quiz_is_deterministic_and_valid():
    arch = build_architecture(_repo())
    quiz = QuizFeature(None, None, lambda _rid: arch)
    first = quiz.generate("r", "seed-1")
    assert first and first == quiz.generate("r", "seed-1")
    for q in first:
        assert q["answer"] in q["options"]
        assert len(set(q["options"])) == len(q["options"])


def test_reranker_demotes_tests_unless_asked():
    code = Chunk("code", {"file_path": "app/security.py"})
    test = Chunk("test", {"file_path": "tests/test_security.py"})
    assert rerank("how is the password hashed", [test, code], 2)[0] is code
    assert rerank("which test checks hashing", [test, code], 2)[0] is test