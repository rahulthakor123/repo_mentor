# Repo Mentor

Paste a public GitHub repo and learn it step by step. Repo Mentor clones the repo, indexes the code, and gives a beginner:

- **Q&A with sources**: answers that link to the exact files and lines.
- **Learning path**: which files to read, in what order, and a first exercise.
- **Setup guide**: install and run steps for Windows PowerShell.
- **Architecture map** (Python repos): a diagram of which file imports which, an endpoint table, and a one-line role for each file.
- **Quiz** (Python repos with at least 4 source files): multiple-choice questions built from the real code.

It runs fully locally with [Ollama](https://ollama.com), so it costs nothing, and the model can be switched to Claude by changing one line in `.env`.

## Design idea

Small local models make things up. So wherever a fact can be computed, **code computes it and the model only explains it**:

| Feature | Computed by code | Written by the model |
|---|---|---|
| Learning path | file order, function names, import links, run command | two sentences per file |
| Setup guide | every command, packages, env variables | descriptions of unfamiliar libraries |
| Architecture map | diagram, endpoint table, "used by N files" | one sentence per file |
| Quiz | questions, options and answers | nothing |
| Q&A | retrieval of the relevant code | the answer, limited to the retrieved code |

## Quick start (Windows PowerShell)

1. Install [Ollama](https://ollama.com), then pull the two models:

   ```powershell
   ollama pull llama3.2
   ollama pull nomic-embed-text
   ```

2. Install the project:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   python -m pip install -e ".[dev]"
   Copy-Item .env.example .env
   ```

   If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` first.

3. Run it:

   ```powershell
   python -m streamlit run ui/app.py
   ```

4. Paste a repo URL in the sidebar and click **Index repo**.

I use `python -m pip` and `python -m streamlit` because plain `pip` and `streamlit` were blocked by a Windows Application Control policy on my machine.

## Settings

All settings live in `.env`:

```
LLM_PROVIDER=ollama
EMBEDDING_PROVIDER=ollama
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_LLM_MODEL=llama3.2
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

`127.0.0.1` is used instead of `localhost` because `localhost` caused long hangs on my Windows machine.

**Switching to Claude** (written but not yet tested): install the extra with `python -m pip install -e ".[claude]"` and set `LLM_PROVIDER=claude` and `ANTHROPIC_API_KEY=...` in `.env`. Embeddings stay on Ollama, since Claude has no embedding API.

When you change the chunker or embedding model, change `index_version` in `src/repo_mentor/config.py`. Old indexes are then ignored and rebuilt.

## How it works

```
GitHub URL -> clone -> filter files -> chunk by function/class -> embed (Ollama)
          -> vector search + re-rank -> LLM answer with file and line sources
```

- **Chunking**: Python files are split with the `ast` module, one chunk per function. Classes over 30 lines and functions over 60 lines are split into their parts. Other file types use 40-line windows.
- **Embeddings**: `nomic-embed-text` with its `search_document:` and `search_query:` prefixes.
- **Vector store**: a small NumPy store that saves to JSON. I replaced ChromaDB because its gRPC library was blocked on my machine, and the store sits behind an interface (`VectorStore`), so it can be swapped back.
- **Re-ranker**: chunks from `tests/` and docs are moved down a few places unless the question mentions tests or docs.

## Evaluation

Retrieval is scored on questions that each name the file and a text snippet that must appear in the retrieved chunk.

- **Evidence Hit@5**: the answer chunk is in the top 5.
- **Hit@1**: it is ranked first.
- **MRR**: the mean of 1 / rank of the first correct chunk.

### Step by step on the WhatsApp repo (4 files, 20 questions)

| Setup | Hit@5 | Hit@1 | MRR |
|---|---|---|---|
| 40-line windows | 0.80 | 0.45 | 0.579 |
| + embedding prefixes | 0.95 | 0.45 | 0.628 |
| + data files filtered out | 0.95 | 0.50 | 0.670 |
| + code-aware chunking | 1.00 | 0.90 | 0.950 |

### Three repos

| Repo | Questions | Windows | Code chunks | Code chunks + re-rank |
|---|---|---|---|---|
| WhatsApp analyzer (4 files) | 20 | 0.95 / 0.50 / 0.670 | 1.00 / 0.90 / 0.950 | 1.00 / 0.90 / 0.950 |
| FastAPI-101, dev set (52 files) | 20 | 0.80 / 0.35 / 0.512 | 0.95 / 0.70 / 0.804 | 0.95 / 0.80 / 0.858 |
| FastAPI-101, held-out (52 files) | 15 | 0.733 / 0.400 / 0.550 | 0.933 / 0.667 / 0.769 | 0.933 / 0.800 / 0.856 |
| Flask DevOps (13 files) | 20 | 0.85 / 0.35 / 0.556 | 0.90 / 0.55 / 0.681 | 0.90 / 0.75 / 0.800 |

Each cell is Hit@5 / Hit@1 / MRR. Code-aware chunking and the re-ranker improved ranking on every repo that has anything to improve.

### Limits of these numbers

- **The author wrote the questions**, after reading each repo. A different author would phrase them differently.
- **Small samples.** One question is worth 0.05 to 0.07.
- **Tuning.** The chunker changes were made after seeing which FastAPI dev questions failed. The held-out set was written before more tuning, but I had seen its misses before designing the re-ranker (its penalty was fixed in advance). The Flask run is the only one where nothing was changed afterwards.
- **Tiny repos.** The Flask repo has 23 chunks, so the top 5 is about a fifth of it.
- **Known weakness:** questions about config files with no function structure, such as Dockerfiles. On the Flask repo the Dockerfile chunk ranked 10th and 11th of 23 for two questions.

### Reproduce

```powershell
python -c "from repo_mentor.ingestion.cloner import clone_repo; clone_repo('https://github.com/iammikek/fastAPI-101.git')"
python evaluation\run_eval.py --chunker simple --k 5 --questions evaluation\questions_fastapi.json
python evaluation\run_eval.py --chunker code --k 5 --questions evaluation\questions_fastapi.json
python evaluation\run_eval.py --chunker code --k 5 --rerank --questions evaluation\questions_fastapi.json
```

Question files: `questions.json` (WhatsApp), `questions_fastapi.json`, `questions_heldout.json`, `questions_flask.json`. Each result is saved in `evaluation/results/`.

## Tests

```powershell
python -m pytest -q
```

The 13 tests cover the file filters, the requirements parser, run-command detection, the chunker, the import graph, edge reduction in the diagram, quiz generation and the re-ranker. They don't need Ollama.

## Known limitations

- Public repos only.
- The architecture map and the quiz read **Python imports only**. Other languages get a message saying so.
- The diagram shows imports, not runtime calls, and hides a link when a longer path already connects two files.
- Endpoint paths include each router's own `prefix=...`. A prefix passed in `include_router(...)` is not detected.
- Indexing stops at 1,500 chunks (`max_chunks`), with code first and docs last. Big repos lose their last chunks.
- There is no re-index button. To refresh a repo, delete its folder in `data\repos` and its files in `data\indexes`.
- The sentences written by the model are not fact-checked. A 3B model can still guess, for example about what a file is for.

## Project layout

```
src/repo_mentor/
  ingestion/   clone, filter, load files; setup facts; import graph; architecture
  chunking/    simple (windows) and code-aware (ast) chunkers
  indexing/    embedder and NumPy vector store
  retrieval/   retriever and re-ranker
  llm/         Ollama and Claude providers behind one interface
  features/    qa, learning_path, setup_guide, architecture_map, quiz
  prompts/     prompts as .md files
ui/app.py      Streamlit interface
evaluation/    questions, scoring script, results
tests/         unit tests
```

To add a feature, add a file in `features/` and a mode in `ui/app.py`.