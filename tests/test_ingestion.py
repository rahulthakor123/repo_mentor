from pathlib import Path

import pytest

from repo_mentor.ingestion.cloner import repo_id_from_url
from repo_mentor.ingestion.filters import should_skip
from repo_mentor.ingestion.loader import SourceFile
from repo_mentor.ingestion.setup_facts import (
    _python_run, build_setup_facts, parse_requirements,
)


def _file(tmp_path, name, size=10):
    p = tmp_path / name
    p.write_bytes(b"x" * size)
    return p


def test_filters(tmp_path):
    f = _file(tmp_path, "f")
    assert not should_skip(Path("src/app.py"), f, 100)
    assert not should_skip(Path("requirements.txt"), f, 100)
    assert should_skip(Path("notes.txt"), f, 100)          # data .txt files are skipped
    assert should_skip(Path("node_modules/a.js"), f, 100)
    assert should_skip(Path("logo.png"), f, 100)
    assert should_skip(Path("data.csv"), f, 100)
    assert should_skip(Path(".gitignore"), f, 100)
    assert should_skip(Path("big.py"), _file(tmp_path, "big", 2048), 1)   # over 1 KB limit


def test_repo_id_from_url():
    assert repo_id_from_url("https://github.com/iammikek/fastAPI-101.git") == "iammikek__fastAPI-101"
    assert repo_id_from_url("https://github.com/pallets/flask") == "pallets__flask"
    with pytest.raises(ValueError):
        repo_id_from_url("https://example.com/nothing")


def test_parse_requirements():
    text = "streamlit\npandas==2.0  # comment\n-r other.txt\n\nrequests>=2\n"
    assert parse_requirements(text) == ["streamlit", "pandas", "requests"]


def test_run_command_detection():
    assert _python_run("main.py", "import streamlit as st", []) == "python -m streamlit run main.py"
    assert _python_run("main.py", "from app.main import app", ["fastapi"]) == \
        "python -m uvicorn main:app --reload"
    assert _python_run("app.py", "app = Flask(__name__)\napp.run(port=1)", ["flask"]) == "python app.py"
    assert _python_run("tool.py", "print('hi')", []) == "python tool.py"


def test_setup_facts_python():
    files = [
        SourceFile("requirements.txt", "text", "streamlit\npandas\n"),
        SourceFile("main.py", "python", "import streamlit as st\n"),
        SourceFile(".env.example", "text", "API_KEY=abc\n"),
    ]
    f = build_setup_facts(files)
    assert f.language == "python"
    assert f.packages == ["streamlit", "pandas"]
    assert f.install_cmd == "python -m pip install -r requirements.txt"
    assert f.run_cmd == "python -m streamlit run main.py"
    assert f.env_vars == ["API_KEY"] and f.has_env_example
    assert not f.has_readme and len(f.notes) == 2     # no README + unpinned versions


def test_setup_facts_node_and_unknown():
    node = build_setup_facts([SourceFile(
        "package.json", "json", '{"dependencies": {"express": "4"}, "scripts": {"start": "node index.js"}}')])
    assert node.language == "node" and node.run_cmd == "npm start" and node.packages == ["express"]
    assert build_setup_facts([]).language == "unknown"