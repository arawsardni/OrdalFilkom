"""Split parsed pages into page-scoped chunks that keep tables and headings together.

Rules (see eval/BASELINE.md for the failures they address):
- A chunk never spans two pages, so every citation points at one page.
- Blocks (paragraphs, list items, tables) are never cut mid-block; a table larger than a chunk is
  split between rows and its header rows are repeated in every piece.
- A heading starts a new chunk and is carried as the chunk's "section", also across pages, so a
  table row like "Ketua | 1500" stays tied to "Eksekutif Mahasiswa, Tingkat Universitas".
"""
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

MAX_CHARS = 1500  # ~400-450 tokens of Indonesian text
MIN_CHARS = 300  # smaller leftovers are merged into the previous chunk of the same page
MIN_PAGE_CHARS = 80  # pages with less text (covers, separators) are skipped
MIN_CHUNK_CHARS = 40  # fragments below this (stray captions, page labels) are dropped

HEADING = re.compile(r"^#{1,6}\s+(.*)$")
TABLE_SEPARATOR = re.compile(r"^\|?\s*:?-{3,}")
DOT_LEADER = re.compile(r"\.{5,}|…{2,}")


def _is_table_of_contents(text: str) -> bool:
    """'Judul bab ........ 23' lines match many queries but answer none of them"""
    leaders = len(DOT_LEADER.findall(text))
    return leaders >= 3 and leaders / (text.count("\n") + 1) > 0.3


@dataclass
class Chunk:
    page: int
    index: int  # position of the chunk within its page
    section: Optional[str]
    text: str


def _strip_markdown(text: str) -> str:
    return re.sub(r"[*_`]+", "", text).strip()


def _blocks(page_text: str) -> List[str]:
    """Paragraphs separated by blank lines; a table (run of '|' lines) is one block."""
    blocks, current, in_table = [], [], False
    for line in page_text.split("\n"):
        is_table = line.lstrip().startswith("|")
        if not line.strip() or (current and is_table != in_table):
            if current:
                blocks.append("\n".join(current))
            current = [line] if line.strip() else []
            in_table = is_table
            continue
        current.append(line)
        in_table = is_table
    if current:
        blocks.append("\n".join(current))
    return blocks


def _split_table(table: str, max_chars: int) -> List[str]:
    lines = table.split("\n")
    header_size = 2 if len(lines) > 1 and TABLE_SEPARATOR.match(lines[1].strip()) else 1
    header, rows = lines[:header_size], lines[header_size:]
    pieces, current = [], list(header)
    for row in rows:
        if len("\n".join(current + [row])) > max_chars and len(current) > header_size:
            pieces.append("\n".join(current))
            current = list(header)
        current.append(row)
    pieces.append("\n".join(current))
    return pieces


def _split_text(text: str, max_chars: int) -> List[str]:
    sentences = re.split(r"(?<=[.;:])\s+|\n", text)
    pieces, current = [], ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > max_chars:
            pieces.append(current)
            current = ""
        current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def _fit(block: str, max_chars: int) -> List[str]:
    if len(block) <= max_chars:
        return [block]
    if block.lstrip().startswith("|"):
        return _split_table(block, max_chars)
    return _split_text(block, max_chars)


def chunk_pages(pages: Iterable[dict], max_chars: int = MAX_CHARS, min_chars: int = MIN_CHARS) -> List[Chunk]:
    """pages: [{page, text}] in document order (output of parsing.parse_pdf)"""
    chunks: List[Chunk] = []
    section: Optional[str] = None
    for page in pages:
        text = page["text"]
        if len(text.strip()) < MIN_PAGE_CHARS:
            continue
        page_chunks: List[Chunk] = []
        current, current_section = [], section

        def flush():
            if current:
                page_chunks.append(Chunk(page["page"], len(page_chunks), current_section, "\n\n".join(current)))

        for block in _blocks(text):
            heading = HEADING.match(block.strip())
            if heading:
                # A heading opens a new chunk unless the current one is still tiny
                if current and len("\n\n".join(current)) >= min_chars:
                    flush()
                    current = []
                section = _strip_markdown(heading.group(1)) or section
                if not current:
                    current_section = section
            for piece in _fit(block, max_chars):
                if current and len("\n\n".join(current + [piece])) > max_chars:
                    flush()
                    current, current_section = [], section
                current.append(piece)
        flush()

        # Merge a small leftover into the previous chunk of the same page when it still fits
        if len(page_chunks) > 1 and len(page_chunks[-1].text) < min_chars:
            last, previous = page_chunks[-1], page_chunks[-2]
            if len(previous.text) + len(last.text) <= max_chars * 1.2:
                previous.text = f"{previous.text}\n\n{last.text}"
                page_chunks.pop()
        page_chunks = [
            c for c in page_chunks
            if len(c.text.strip()) >= MIN_CHUNK_CHARS and not _is_table_of_contents(c.text)
        ]
        for index, chunk in enumerate(page_chunks):
            chunk.index = index
        chunks.extend(page_chunks)
    return chunks
