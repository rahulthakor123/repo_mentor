import argparse
import json
from pathlib import Path

from repo_mentor.retrieval.reranker import rerank
from repo_mentor.chunking.simple_chunker import SimpleChunker
from repo_mentor.chunking.code_chunker import CodeChunker
from repo_mentor.config import settings
from repo_mentor.indexing.embedder import get_embedder
from repo_mentor.indexing.stores.numpy_store import NumpyStore
from repo_mentor.ingestion.loader import load_repo_files

HERE = Path(__file__).resolve().parent
# later (Phase 2.5): CHUNKERS["code"] = CodeChunker
CHUNKERS = {"simple": SimpleChunker, "code": CodeChunker}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunker", default="simple", choices=list(CHUNKERS))
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--rerank", action="store_true")
    ap.add_argument("--questions", default=str(HERE / "questions.json"))
    args = ap.parse_args()

    data = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    repo_id, questions = data["repo"], data["questions"]

    files = load_repo_files(settings.repos_dir / repo_id)
    texts = {f.path: f.text for f in files}

    # sanity check: every evidence snippet must exist in the repo
    bad = [x for x in questions if x["evidence"] not in texts.get(x["file"], "")]
    for x in bad:
        print(f"BAD QUESTION (evidence not found in {x['file']}): {x['q']}")
    questions = [x for x in questions if x not in bad]

    store = NumpyStore(get_embedder())
    key = f"{repo_id}__eval_{args.chunker}"
    chunker = CHUNKERS[args.chunker]()
    chunks = [c for f in files for c in chunker.chunk(f)]
    print(f"{args.chunker}: {len(chunks)} chunks, {len(questions)} questions, k={args.k}")
    store.add(key, chunks)

    rows, file_hits, ev_hits, top1, rr = [], 0, 0, 0, 0.0
    for x in questions:
        got = (rerank(x["q"], store.search(key, x["q"], args.k * 4), args.k)
               if args.rerank else store.search(key, x["q"], args.k))
        file_rank = next((i for i, c in enumerate(got, 1)
                          if c.metadata["file_path"] == x["file"]), None)
        ev_rank = next((i for i, c in enumerate(got, 1)
                        if c.metadata["file_path"] == x["file"] and x["evidence"] in c.text), None)
        file_hits += file_rank is not None
        ev_hits += ev_rank is not None
        top1 += ev_rank == 1
        rr += 1 / ev_rank if ev_rank else 0
        rows.append({"q": x["q"], "file_rank": file_rank, "evidence_rank": ev_rank,
                     "retrieved": [f"{c.metadata['file_path']}:{c.metadata['start_line']}" for c in got]})

    n = len(questions)
    summary = {
        "chunker": args.chunker, "k": args.k, "questions": n, "chunks": len(chunks),
        f"file_hit@{args.k}": round(file_hits / n, 3),
        f"evidence_hit@{args.k}": round(ev_hits / n, 3),
        "evidence_hit@1": round(top1 / n, 3),
        "mrr": round(rr / n, 3),
    }

    print("\nMISSES (answer not in top-k):")
    for r in rows:
        if r["evidence_rank"] is None:
            print(f"- {r['q']}\n    got: {r['retrieved']}")
    print("\n" + json.dumps(summary, indent=2))

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / f"{repo_id}_{args.chunker}{'_rerank' if args.rerank else ''}_k{args.k}.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()