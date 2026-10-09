"""
Evaluate the RAG pipeline against eval/dataset.jsonl.

    uv run scripts/eval.py --check-dataset   # verify reference pages against the raw PDFs (no API calls)
    uv run scripts/eval.py                   # retrieval metrics only (fast, embeddings only)
    uv run scripts/eval.py --answers         # + generate answers, grade correctness and groundedness (slow)

Answer metrics:
- correctness vs the reference answer (Gemini judge)
- groundedness (the primary metric, see docs/PRODUCT.md):
  - faithfulness: share of the answer's claims supported by the context the LLM received (Gemini judge)
  - displayed source hit: a source shown to the user (a page the answer cites) is one of the
    reference pages (deterministic)
  - citations: answers that cite sources, and answers citing numbers outside the given sources (deterministic)
  - refusals: out-of-scope questions refused, answerable ones not refused (deterministic)

The judge runs on Gemini so evals don't spend the live app's Groq quota (needs GOOGLE_API_KEY).
Results are written to eval/results/<timestamp>_<label>.json so runs can be compared over time.
"""
import os
import re
import sys
import json
import time
import logging
import argparse
import urllib.error
import urllib.request
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

FAITHFULNESS_PROMPT = """Kamu memeriksa apakah jawaban chatbot didukung oleh KONTEKS dokumen yang diberikan kepada chatbot itu.

KONTEKS:
{context}

PERTANYAAN: {question}

JAWABAN CHATBOT:
{answer}

Langkah:
1. Pecah jawaban menjadi klaim faktual atomik (angka, syarat, aturan, prosedur, nama/tahun dokumen). Abaikan kalimat pembuka/penutup, saran umum, dan pernyataan bahwa informasi tidak tersedia.
2. Untuk setiap klaim, tentukan apakah klaim itu didukung oleh KONTEKS. Gunakan hanya KONTEKS, bukan pengetahuan umum. Klaim yang bertentangan dengan konteks atau tidak ada di konteks dianggap tidak didukung.

Balas HANYA dengan JSON: {{"claims": [{{"claim": "<klaim singkat>", "supported": true}}]}}"""

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Baseline heuristic: refusal phrasing near the start of the answer. Once the generation
# prompt prescribes an exact refusal sentence, match that sentence instead.
REFUSAL_PATTERN = re.compile(
    r"tidak (tersedia|ditemukan|tercantum|disebutkan)"
    r"|tidak (ada|terdapat) (informasi|ketentuan|data|keterangan|aturan)"
    r"|tidak (dapat |bisa )?(menemukan|menjawab)|tidak memiliki informasi",
    re.IGNORECASE,
)


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


def gemini_json(model, prompt, max_attempts=4):
    """Call the Gemini judge and parse its JSON reply, retrying the free tier's transient errors"""
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }).encode()
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(
            GEMINI_URL.format(model=model),
            data=body,
            headers={"Content-Type": "application/json", "x-goog-api-key": Settings.get_google_api_key()},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                reply = json.loads(response.read())
            return json.loads(reply["candidates"][0]["content"]["parts"][0]["text"])
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 503) or attempt == max_attempts:
                raise
        except (KeyError, IndexError, json.JSONDecodeError):
            if attempt == max_attempts:
                raise
        time.sleep(15 * attempt)


def judge_correctness(judge_model, item, answer):
    prompt = JUDGE_PROMPT.format(question=item["question"], reference=item["reference_answer"], answer=answer)
    try:
        parsed = gemini_json(judge_model, prompt)
    except Exception as e:
        # Judge failures are not answer-quality signals, so they are kept out of the score
        return "error", f"judge error: {str(e)[:150]}"
    if parsed.get("verdict") not in VERDICT_SCORE:
        return "error", f"judge output unparseable: {str(parsed)[:150]}"
    return parsed["verdict"], parsed.get("reason", "")


def format_context(nodes):
    return "\n\n".join(
        f"[{i}] {n.metadata.get('file_name')} hal. {n.metadata.get('page_label')}\n{n.get_content()}"
        for i, n in enumerate(nodes, 1)
    )


def judge_faithfulness(judge_model, item, answer, nodes):
    """Share of the answer's factual claims supported by the context the LLM received"""
    prompt = FAITHFULNESS_PROMPT.format(context=format_context(nodes), question=item["question"], answer=answer)
    try:
        claims = gemini_json(judge_model, prompt).get("claims", [])
    except Exception as e:
        return None, [], f"judge error: {str(e)[:150]}"
    if not claims:
        return None, [], None  # nothing factual to check
    supported = sum(1 for c in claims if c.get("supported") is True)
    return supported / len(claims), claims, None


def refusal_phrase(answer):
    """The refusal phrase in the answer's first sentence, if any. Answers that give content and
    only mention a missing detail later on are not refusals."""
    first_sentence = re.split(r"(?<=[.!?])\s|\n", answer.strip(), maxsplit=1)[0][:300]
    match = REFUSAL_PATTERN.search(first_sentence)
    return match.group(0) if match else None


_PDF_PATHS = None


def _raw_page_text(file_name, page):
    """Text of a page in the original PDF (not the parsed chunks, which can contain invented text)"""
    import pymupdf

    global _PDF_PATHS
    if _PDF_PATHS is None:
        _PDF_PATHS = {p.name: p for p in Path(Settings.DATASET_DIR).rglob("*.pdf")}
    if file_name not in _PDF_PATHS or not str(page).isdigit():
        return ""
    with pymupdf.open(_PDF_PATHS[file_name]) as pdf:
        index = int(page) - 1
        return pdf[index].get_text() if 0 <= index < pdf.page_count else ""


def displayed_source_hit(sources, item):
    """Whether a source shown to the user actually backs the answer: it is one of the reference
    pages, or its original PDF page contains the item's evidence text. The reference list can't
    name every page that states a fact, so the evidence check avoids penalising valid citations."""
    normalize = lambda text: re.sub(r"\s+", " ", text).lower()
    for s in sources or []:
        if any(s["file_name"] == ref["file"] and str(s["page"]) in map(str, ref["pages"]) for ref in item["sources"]):
            return True
        if item.get("evidence") and normalize(item["evidence"]) in normalize(_raw_page_text(s["file_name"], s["page"])):
            return True
    return False


def evaluate_answers(engine, items, judge_model, sleep_seconds):
    from src.core.chat_handler import ChatHandler

    handler = ChatHandler(engine)
    results = []
    for i, item in enumerate(items):
        answer, sources, latency, error = generate_answer(handler, item["question"])
        result = {"id": item["id"], "type": item["type"], "latency_s": round(latency, 1), "answer": answer}
        if error:
            # Infrastructure failures are not answer-quality signals, so keep them out of the score
            result.update(verdict="error", reason=f"generation error: {error}", generated=False)
        else:
            nodes = handler.last_nodes
            verdict, reason = judge_correctness(judge_model, item, answer)
            refusal = refusal_phrase(answer)
            refused = refusal is not None
            faithfulness, claims, faith_error = (None, [], None) if refused else judge_faithfulness(judge_model, item, answer, nodes)
            result.update(
                verdict=verdict,
                reason=reason,
                generated=True,
                refused=refused,
                refusal_phrase=refusal,
                displayed_sources=sources,
                displayed_source_hit=displayed_source_hit(sources, item) if item["sources"] else None,
                cited_pages=len(sources or []),
                invalid_citations=handler.last_invalid_citations,
                faithfulness=round(faithfulness, 3) if faithfulness is not None else None,
                unsupported_claims=[c.get("claim") for c in claims if c.get("supported") is not True],
                faithfulness_error=faith_error,
                context_pages=[f"{n.metadata.get('file_name')} p{n.metadata.get('page_label')}" for n in nodes],
            )
        faith = "-" if result.get("faithfulness") is None else f"{result['faithfulness']:.2f}"
        print(f"  {item['id']:8s} {result['verdict']:9s} faith={faith:4s} hit={str(result.get('displayed_source_hit')):5s} "
              f"refused={str(result.get('refused')):5s} {latency:5.1f}s  {result['reason'][:70]}")
        results.append(result)
        if i < len(items) - 1:
            time.sleep(sleep_seconds)  # stay under Groq's tokens-per-minute limit
    return results


def _rate(values):
    values = list(values)
    return round(sum(values) / len(values), 3) if values else None


def summarize_answers(results):
    generated = [r for r in results if r["generated"]]
    graded = [r for r in generated if r["verdict"] in VERDICT_SCORE]
    by_type = defaultdict(list)
    for r in graded:
        by_type[r["type"]].append(VERDICT_SCORE[r["verdict"]])
    answerable = [r for r in generated if r["type"] != "out_of_scope"]
    out_of_scope = [r for r in generated if r["type"] == "out_of_scope"]
    faithfulness = [r["faithfulness"] for r in generated if r["faithfulness"] is not None]
    latencies = sorted(r["latency_s"] for r in generated)
    return {
        "groundedness": {
            "faithfulness": _rate(faithfulness),
            "fully_grounded": _rate(f == 1.0 for f in faithfulness),
            "displayed_source_hit": _rate(r["displayed_source_hit"] for r in answerable),
            "answers_with_citations": _rate(r["cited_pages"] > 0 for r in generated if not r["refused"]),
            "answers_with_invalid_citations": _rate(r["invalid_citations"] > 0 for r in generated if not r["refused"]),
            "out_of_scope_refusal": _rate(r["refused"] for r in out_of_scope),
            "false_refusal": _rate(r["refused"] for r in answerable),
        },
        "correctness": {
            "score": _rate(VERDICT_SCORE[r["verdict"]] for r in graded),
            "correct": sum(r["verdict"] == "correct" for r in graded),
            "partial": sum(r["verdict"] == "partial" for r in graded),
            "incorrect": sum(r["verdict"] == "incorrect" for r in graded),
            "score_by_type": {t: round(sum(s) / len(s), 3) for t, s in sorted(by_type.items())},
        },
        "errors": {
            "generation": len(results) - len(generated),
            "correctness_judge": len(generated) - len(graded),
            "faithfulness_judge": sum(1 for r in generated if r["faithfulness_error"]),
        },
        "median_latency_s": latencies[len(latencies) // 2] if latencies else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check-dataset", action="store_true", help="only verify the dataset against the raw PDFs")
    parser.add_argument("--answers", action="store_true", help="also generate and judge answers")
    parser.add_argument("--only", help="comma-separated item ids to run")
    parser.add_argument("--top-k", type=int, default=Settings.SIMILARITY_TOP_K)
    parser.add_argument("--judge-model", default=Settings.JUDGE_MODEL)
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
