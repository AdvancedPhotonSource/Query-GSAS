"""
Evaluation script: run all 40 questions against the ChromaDB index and compute
Recall@1, Recall@3, Recall@6, and MRR per category and overall.

Usage:
    python evaluation/run_eval.py [--db PATH] [--out results.json]
"""

import json
import os
import sys
from pathlib import Path

DEFAULT_DB = Path.home() / ".GSASII" / "gsas_query" / "chroma_db"
COLLECTION = "gsasii_docs"
TOP_K = 6

def load_questions(path):
    with open(path) as f:
        return json.load(f)["questions"]

def build_collection(db_path):
    import chromadb
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from gsas_query._embed import get_embedding_function
    client = chromadb.PersistentClient(path=str(db_path))
    col = client.get_collection(COLLECTION)
    ef = get_embedding_function()
    return col, ef

FETCH_K = 30  # over-fetch then dedup by URL, matching production rag.py behaviour

def retrieve(col, ef, question, k=TOP_K):
    emb = ef([question])[0]
    fetch_k = min(FETCH_K, col.count())
    results = col.query(
        query_embeddings=[emb],
        n_results=fetch_k,
        include=["metadatas", "distances"],
    )
    # URL-diversity dedup: keep best chunk per unique URL, then top-k
    seen_urls = {}
    ordered = []
    for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
        url = meta.get("url", "")
        if url not in seen_urls:
            seen_urls[url] = dist
            ordered.append(url)
    return ordered[:k]

def hit_at_k(retrieved_urls, gt_urls, k):
    for url in retrieved_urls[:k]:
        for gt in gt_urls:
            # match on URL prefix (ignore fragment differences)
            if url.rstrip("/") == gt.rstrip("/") or url.startswith(gt.rstrip("/")) or gt.startswith(url.rstrip("/")):
                return True
    return False

def reciprocal_rank(retrieved_urls, gt_urls):
    for i, url in enumerate(retrieved_urls, start=1):
        for gt in gt_urls:
            if url.rstrip("/") == gt.rstrip("/") or url.startswith(gt.rstrip("/")) or gt.startswith(url.rstrip("/")):
                return 1.0 / i
    return 0.0

def evaluate(questions, col, ef):
    categories = {}
    all_results = []

    for q in questions:
        qid = q["id"]
        cat = q["category"]
        question_text = q["question"]
        gt_urls = q["ground_truth_urls"]

        retrieved = retrieve(col, ef, question_text)
        h1 = hit_at_k(retrieved, gt_urls, 1)
        h3 = hit_at_k(retrieved, gt_urls, 3)
        h6 = hit_at_k(retrieved, gt_urls, 6)
        rr = reciprocal_rank(retrieved, gt_urls)

        row = {
            "id": qid,
            "category": cat,
            "question": question_text,
            "gt_urls": gt_urls,
            "retrieved_urls": retrieved,
            "hit@1": h1,
            "hit@3": h3,
            "hit@6": h6,
            "rr": rr,
        }
        all_results.append(row)

        if cat not in categories:
            categories[cat] = []
        categories[cat].append(row)

        status = f"  Q{qid:2d} [{cat:12s}] @1={'Y' if h1 else 'N'} @3={'Y' if h3 else 'N'} @6={'Y' if h6 else 'N'} RR={rr:.2f}"
        print(status)
        print(f"    retrieved[0]: {retrieved[0] if retrieved else '(none)'}")

    # Aggregate
    def agg(rows):
        n = len(rows)
        return {
            "n": n,
            "recall@1": round(sum(r["hit@1"] for r in rows) / n, 3),
            "recall@3": round(sum(r["hit@3"] for r in rows) / n, 3),
            "recall@6": round(sum(r["hit@6"] for r in rows) / n, 3),
            "mrr": round(sum(r["rr"] for r in rows) / n, 3),
        }

    summary = {"All": agg(all_results)}
    for cat, rows in sorted(categories.items()):
        summary[cat] = agg(rows)

    return all_results, summary

def main():
    db_path = DEFAULT_DB
    out_path = Path(__file__).parent / "eval_results.json"

    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--db" and i + 1 < len(sys.argv) - 1:
            db_path = Path(sys.argv[i + 2])
        if arg == "--out" and i + 1 < len(sys.argv) - 1:
            out_path = Path(sys.argv[i + 2])

    q_path = Path(__file__).parent / "questions.json"
    questions = load_questions(q_path)

    print(f"Loading index from: {db_path}")
    col, ef = build_collection(db_path)
    print(f"Index has {col.count()} chunks\n")
    print(f"Running {len(questions)} queries...\n")

    results, summary = evaluate(questions, col, ef)

    output = {"summary": summary, "per_question": results}
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print("\n=== SUMMARY ===")
    cats_order = ["All", "Rietveld", "Sequential", "Structure", "Calibration", "Scripting", "Export"]
    header = f"{'Category':<20} {'N':>4} {'R@1':>6} {'R@3':>6} {'R@6':>6} {'MRR':>6}"
    print(header)
    print("-" * len(header))
    for cat in cats_order:
        if cat in summary:
            s = summary[cat]
            print(f"{cat:<20} {s['n']:>4} {s['recall@1']:>6.3f} {s['recall@3']:>6.3f} {s['recall@6']:>6.3f} {s['mrr']:>6.3f}")

    print(f"\nFull results written to: {out_path}")

if __name__ == "__main__":
    main()
