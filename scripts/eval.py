"""
Evaluate the RAG pipeline against eval/dataset.jsonl.

    uv run scripts/eval.py --check-dataset   # verify reference pages against the raw PDFs (no API calls)
    uv run scripts/eval.py                   # retrieval metrics only (fast, embeddings only)
    uv run scripts/eval.py --answers         # + generate answers and grade them with an LLM judge (slow)

Results are written to eval/results/<timestamp>_<label>.json so runs can be compared over time.
"""
import os
import re
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding="utf-8")

from src.config.settings import Settings

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

DATASET_PATH = Path("eval/dataset.jsonl")
RESULTS_DIR = Path("eval/results")
HIT_AT = [1, 3, 5, 10, 30]
VERDICT_SCORE = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}

JUDGE_PROMPT = """Kamu adalah penilai jawaban chatbot akademik. Bandingkan JAWABAN CHATBOT dengan JAWABAN REFERENSI.

PERTANYAAN: {question}

JAWABAN REFERENSI: {reference}

JAWABAN CHATBOT: {answer}

Aturan penilaian:
- "correct": semua fakta inti di referensi ada di jawaban chatbot dan tidak ada fakta yang bertentangan.
- "partial": sebagian fakta inti benar, tapi ada yang hilang ATAU ada tambahan klaim yang tidak didukung referensi.
- "incorrect": fakta inti salah/bertentangan, atau chatbot tidak menjawab.
- Jika referensi menyatakan informasi tidak tersedia: "correct" hanya jika chatbot menyatakan informasinya tidak ada dan tidak mengarang angka/fakta.
- Abaikan gaya, panjang, dan format jawaban.

Balas HANYA dengan JSON satu baris: {{"verdict": "correct|partial|incorrect", "reason": "<alasan singkat>"}}"""


def load_dataset():
    with open(DATASET_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def is_relevant(node, sources):
    """A retrieved chunk counts as a hit if it comes from one of the reference file/page pairs"""
    file_name = node.metadata.get("file_name")
    page = str(node.metadata.get("page_label"))
    return any(file_name == s["file"] and page in map(str, s["pages"]) for s in sources)


def check_dataset(items):
    """Make sure every reference page really contains the evidence text in the original PDF"""
    import pymupdf

    pdf_paths = {p.name: p for p in Path(Settings.DATASET_DIR).rglob("*.pdf")}
    normalize = lambda t: re.sub(r"\s+", " ", t).lower()
    ok = True
    for item in items:
        if not item["sources"]:
            continue
        found = []
        for src in item["sources"]:
            if src["file"] not in pdf_paths:
                print(f"[FAIL] {item['id']}: file not found: {src['file']}")
                ok = False
                continue
            pdf = pymupdf.open(pdf_paths[src["file"]])
            for page in src["pages"]:
                if normalize(item["evidence"]) in normalize(pdf[page - 1].get_text()):
                    found.append(f"{src['file']} p{page}")
        if found:
            print(f"[ OK ] {item['id']}: '{item['evidence']}' found in {', '.join(found)}")
        else:
            print(f"[FAIL] {item['id']}: '{item['evidence']}' not found on any reference page")
            ok = False
    return ok


def evaluate_retrieval(engine, items, top_k):
    retriever = engine.get_retriever(top_k)
    results = []
    for item in items:
        if not item["sources"]:
            continue
        nodes = retriever.retrieve(item["question"])
        rank = next((i for i, n in enumerate(nodes, 1) if is_relevant(n, item["sources"])), None)
        results.append({
            "id": item["id"],
            "type": item["type"],
            "rank": rank,
            "top": [
                {"file": n.metadata.get("file_name"), "page": n.metadata.get("page_label"), "score": round(n.score or 0, 4)}
                for n in nodes[:10]
            ],
        })
        print(f"  {item['id']:8s} rank={rank if rank else '-':>3}  top1={results[-1]['top'][0]['file']} p{results[-1]['top'][0]['page']}")
    return results


def summarize_retrieval(results):
    n = len(results)
    summary = {f"hit@{k}": round(sum(1 for r in results if r["rank"] and r["rank"] <= k) / n, 3) for k in HIT_AT}
    summary["mrr"] = round(sum(1 / r["rank"] for r in results if r["rank"]) / n, 3)
    return summary


def generate_answer(handler, question, max_attempts=3, wait=60):
    for attempt in range(1, max_attempts + 1):
        handler.reset_memory()
        start = time.time()
        text, sources, error, _ = handler.process_query(question)
        if not error:
            return text, sources, time.time() - start, None
        if "TPD" in error:
            # Daily token quota: retrying is pointless, and the live app shares this quota
            sys.exit(f"Daily token limit reached ({error}). Try again tomorrow or use --only for a subset.")
        transient = "Rate Limit" in error or "timed out" in error.lower()
        if not transient or attempt == max_attempts:
            return None, None, time.time() - start, error
        print(f"    transient error ({error[:60]}), waiting {wait}s...")
        time.sleep(wait)


def judge_answer(judge_llm, item, answer):
    prompt = JUDGE_PROMPT.format(question=item["question"], reference=item["reference_answer"], answer=answer)
    raw = judge_llm.complete(prompt).text
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
    match = re.search(r"\{.*\}", raw, re.S)
    try:
        parsed = json.loads(match.group(0))
        if parsed.get("verdict") in VERDICT_SCORE:
            return parsed["verdict"], parsed.get("reason", "")
    except (AttributeError, json.JSONDecodeError):
        pass
    return "incorrect", f"judge output unparseable: {raw[:200]}"


def evaluate_answers(engine, items, judge_model, sleep_seconds):
    from llama_index.llms.groq import Groq
    from src.core.chat_handler import ChatHandler

    handler = ChatHandler(engine.get_engine())
    judge_llm = Groq(model=judge_model, api_key=Settings.get_groq_api_key(), temperature=0)
    results = []
    for i, item in enumerate(items):
        answer, sources, latency, error = generate_answer(handler, item["question"])
        if error:
            # Infrastructure failures are not answer-quality signals, so keep them out of the score
            verdict, reason = "error", f"generation error: {error}"
        else:
            verdict, reason = judge_answer(judge_llm, item, answer)
        results.append({
            "id": item["id"],
            "type": item["type"],
            "verdict": verdict,
            "reason": reason,
            "latency_s": round(latency, 1),
            "answer": answer,
            "displayed_sources": sources,
        })
        print(f"  {item['id']:8s} {verdict:9s} {latency:5.1f}s  {reason[:90]}")
        if i < len(items) - 1:
            time.sleep(sleep_seconds)  # stay under Groq's tokens-per-minute limit
    return results


def summarize_answers(results):
    graded = [r for r in results if r["verdict"] != "error"]
    by_type = defaultdict(list)
    for r in graded:
        by_type[r["type"]].append(VERDICT_SCORE[r["verdict"]])
    latencies = sorted(r["latency_s"] for r in graded)
    return {
        "score": round(sum(VERDICT_SCORE[r["verdict"]] for r in graded) / len(graded), 3),
        "correct": sum(r["verdict"] == "correct" for r in results),
        "partial": sum(r["verdict"] == "partial" for r in results),
        "incorrect": sum(r["verdict"] == "incorrect" for r in results),
        "errors": len(results) - len(graded),
        "score_by_type": {t: round(sum(s) / len(s), 3) for t, s in sorted(by_type.items())},
        "median_latency_s": latencies[len(latencies) // 2],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check-dataset", action="store_true", help="only verify the dataset against the raw PDFs")
    parser.add_argument("--answers", action="store_true", help="also generate and judge answers")
    parser.add_argument("--only", help="comma-separated item ids to run")
    parser.add_argument("--top-k", type=int, default=Settings.SIMILARITY_TOP_K)
    parser.add_argument("--judge-model", default=Settings.FALLBACK_MODELS[0][0])
    parser.add_argument("--sleep", type=int, default=30, help="seconds between answer generations")
    parser.add_argument("--label", default="run", help="short name for this run, used in the results filename")
    args = parser.parse_args()

    items = load_dataset()
    if args.only:
        wanted = set(args.only.split(","))
        items = [i for i in items if i["id"] in wanted]

    if args.check_dataset:
        sys.exit(0 if check_dataset(items) else 1)

    from src.core.rag_engine import RAGEngine
    engine = RAGEngine()

    output = {
        "label": args.label,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "config": {
            "index": Settings.INDEX_NAME,
            "embedding_model": Settings.EMBEDDING_MODEL,
            "llm": Settings.LLM_MODEL,
            "judge_model": args.judge_model if args.answers else None,
            "top_k": args.top_k,
            "dataset_size": len(items),
        },
    }

    print(f"\nRetrieval (top_k={args.top_k})")
    retrieval = evaluate_retrieval(engine, items, args.top_k)
    output["retrieval"] = {"summary": summarize_retrieval(retrieval), "items": retrieval}

    if args.answers:
        print(f"\nAnswers (llm={Settings.LLM_MODEL}, judge={args.judge_model})")
        answers = evaluate_answers(engine, items, args.judge_model, args.sleep)
        output["answers"] = {"summary": summarize_answers(answers), "items": answers}

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"{datetime.now():%Y%m%d-%H%M}_{args.label}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== Summary ===")
    print("Retrieval:", output["retrieval"]["summary"])
    if args.answers:
        print("Answers:  ", output["answers"]["summary"])
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
