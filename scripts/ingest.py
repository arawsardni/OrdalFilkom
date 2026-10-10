"""
Ingest the PDFs in static/dataset into Pinecone.

    uv run --group ingest scripts/ingest.py --dry-run            # parse + chunk + stats, no embedding
    uv run --group ingest scripts/ingest.py                      # incremental: only new/changed PDFs
    uv run --group ingest scripts/ingest.py --rebuild            # re-embed every PDF
    uv run --group ingest scripts/ingest.py --index NAME         # target another index (default: Settings.INDEX_NAME)

Pipeline: pymupdf4llm parsing (src/ingest/parsing.py) -> page-scoped chunks that keep tables and
headings together (src/ingest/chunking.py) -> Pinecone inference embeddings -> Pinecone upsert.
Document title, scope and section from static/dataset/catalog.json are embedded with each chunk.

A manifest per index (data/ingest_manifest_<index>.json) records each PDF's hash and vector ids,
so unchanged PDFs are skipped and the vectors of changed or removed PDFs are deleted first.
Embedding tokens count against Pinecone's monthly free allowance (5M), so prefer incremental runs.
"""
import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from llama_index.core.schema import TextNode, MetadataMode, NodeRelationship, RelatedNodeInfo
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

from src.config.settings import Settings as AppSettings
from src.core.embeddings import PineconeEmbedding
from src.ingest.chunking import chunk_pages
from src.ingest.parsing import file_hash, parse_pdf
from src.utils.catalog import document_info, load_catalog

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV", "us-east-1")

BATCH_SIZE = 96  # max inputs per Pinecone embed call
MAX_BATCH_ATTEMPTS = 5
# Embedded with the chunk text; everything else is kept out of the embedding and the prompt
EMBED_METADATA_KEYS = ["document", "scope", "section"]


def build_nodes(pdf: Path):
    """Chunk one PDF into TextNodes with deterministic ids (<file stem>-p<page>-c<index>)"""
    info = document_info(pdf.name)
    title = info["title"] + (f" ({info['year']})" if info.get("year") else "")
    scope = ", ".join(str(v) for v in (info.get("program"), info.get("level")) if v)
    nodes = []
    for chunk in chunk_pages(parse_pdf(pdf)):
        metadata = {
            "file_name": pdf.name,
            "page_label": str(chunk.page),
            "category": pdf.parent.name,
            "year": info.get("year") or 0,
            "status": info.get("status", "berlaku"),
            "document": title,
            "scope": scope,
            "section": chunk.section or "",
        }
        node = TextNode(
            id_=f"{pdf.stem}-p{chunk.page:03d}-c{chunk.index}",
            text=chunk.text,
            metadata=metadata,
            excluded_embed_metadata_keys=[k for k in metadata if k not in EMBED_METADATA_KEYS],
            excluded_llm_metadata_keys=list(metadata),
        )
        node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=pdf.stem)
        nodes.append(node)
    return nodes


def embed_and_upsert(nodes, embed_model, vector_store):
    for start in range(0, len(nodes), BATCH_SIZE):
        batch = nodes[start:start + BATCH_SIZE]
        for attempt in range(1, MAX_BATCH_ATTEMPTS + 1):
            try:
                texts = [n.get_content(metadata_mode=MetadataMode.EMBED) for n in batch]
                for node, embedding in zip(batch, embed_model.get_text_embedding_batch(texts)):
                    node.embedding = embedding
                vector_store.add(batch)
                break
            except Exception as e:
                logger.error(f"Batch at {start} failed (attempt {attempt}/{MAX_BATCH_ATTEMPTS}): {e}")
                if attempt == MAX_BATCH_ATTEMPTS:
                    raise
                time.sleep(30 * attempt)


def delete_vectors(pinecone_index, ids):
    for start in range(0, len(ids), 1000):
        pinecone_index.delete(ids=ids[start:start + 1000])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--index", default=AppSettings.INDEX_NAME)
    parser.add_argument("--rebuild", action="store_true", help="re-embed every PDF, ignoring the manifest")
    parser.add_argument("--dry-run", action="store_true", help="parse and chunk only; no embedding or upsert")
    args = parser.parse_args()

    pdfs = sorted(Path(AppSettings.DATASET_DIR).rglob("*.pdf"))
    missing = [p.name for p in pdfs if p.name not in load_catalog()]
    if missing:
        print(f"WARNING: not in catalog.json (titles fall back to file names): {missing}")

    if args.dry_run:
        total_chunks = total_chars = 0
        for pdf in pdfs:
            nodes = build_nodes(pdf)
            chars = sum(len(n.get_content(metadata_mode=MetadataMode.EMBED)) for n in nodes)
            total_chunks += len(nodes)
            total_chars += chars
            print(f"  {pdf.name:55s} {len(nodes):5d} chunks")
        # ~3.5 characters per token for Indonesian text with llama-text-embed-v2
        print(f"Total: {len(pdfs)} PDFs, {total_chunks} chunks, ~{total_chars // 3.5 / 1e6:.2f}M embedding tokens")
        return

    if not PINECONE_API_KEY:
        sys.exit("PINECONE_API_KEY missing in .env")

    pc = Pinecone(api_key=PINECONE_API_KEY)
    if args.index not in [i.name for i in pc.list_indexes()]:
        print(f"Creating Pinecone index {args.index}")
        pc.create_index(
            name=args.index,
            dimension=AppSettings.EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region=PINECONE_ENV),
        )
        while not pc.describe_index(args.index).status.ready:
            time.sleep(2)
    pinecone_index = pc.Index(args.index)
    vector_store = PineconeVectorStore(pinecone_index=pinecone_index)
    embed_model = PineconeEmbedding(
        model_name=AppSettings.EMBEDDING_MODEL,
        api_key=PINECONE_API_KEY,
        dimension=AppSettings.EMBEDDING_DIM,
    )

    manifest_path = Path(f"data/ingest_manifest_{args.index}.json")
    manifest = {} if args.rebuild or not manifest_path.exists() else json.loads(manifest_path.read_text(encoding="utf-8"))

    def save_manifest():
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    # PDFs that were removed from the dataset
    current = {p.name for p in pdfs}
    for name in [n for n in manifest if n not in current]:
        print(f"Removing vectors of deleted PDF {name}")
        delete_vectors(pinecone_index, manifest[name]["ids"])
        del manifest[name]
        save_manifest()

    for pdf in pdfs:
        digest = file_hash(pdf)
        if manifest.get(pdf.name, {}).get("sha256") == digest:
            continue
        start = time.time()
        nodes = build_nodes(pdf)
        if pdf.name in manifest:
            delete_vectors(pinecone_index, manifest[pdf.name]["ids"])
        embed_and_upsert(nodes, embed_model, vector_store)
        manifest[pdf.name] = {"sha256": digest, "ids": [n.id_ for n in nodes]}
        save_manifest()  # after every PDF, so an interrupted run resumes where it stopped
        print(f"  {pdf.name:55s} {len(nodes):5d} chunks  {time.time() - start:5.0f}s")

    print(f"Done. Index {args.index}: {pinecone_index.describe_index_stats().total_vector_count} vectors")


if __name__ == "__main__":
    main()
