"""Numbered sources for the prompt and resolution of the [n] citations the LLM writes back."""
import html
import re
from typing import Dict, List, Tuple

from src.config.prompts import SOURCE_TEMPLATE
from src.utils.catalog import document_info

# A run of adjacent markers such as [1] or [2][3]; also tolerates [2, 3]
CITATION_PATTERN = re.compile(r"(?:\[\d+(?:\s*,\s*\d+)*\])+")
# gpt-oss often falls back to its native style: 【1】 or 【1†L3-L5】
NATIVE_CITATION_PATTERN = re.compile(r"【(\d+)(?:†[^】]*)?】")
WORD_PATTERN = re.compile(r"[0-9A-Za-zÀ-ÿ]+")
HIGHLIGHT_WORDS = 5


def document_title(file_name: str) -> Tuple[str, str]:
    """Title and year from the document catalog, e.g. ('Kurikulum S1 Teknik Informatika', '2024')"""
    info = document_info(file_name)
    return info["title"], str(info["year"]) if info.get("year") else ""


def build_sources_block(nodes) -> str:
    """Numbered source blocks for the system prompt, in retrieval order"""
    blocks = []
    for number, node in enumerate(nodes, 1):
        file_name = node.metadata.get("file_name", "")
        title, year = document_title(file_name)
        issuer = document_info(file_name).get("issuer")
        blocks.append(SOURCE_TEMPLATE.format(
            number=number,
            title=title,
            year=year or "-",
            # Lets the LLM apply the prodi > fakultas > universitas hierarchy from the prompt
            issuer=f", aturan {issuer}" if issuer else "",
            page=node.metadata.get("page_label", "?"),
            section=f", bagian: {node.metadata['section']}" if node.metadata.get("section") else "",
            # LlamaParse stores some characters as HTML entities ("IP &#x3C; 1,50")
            text=html.unescape(node.get_content()).strip(),
        ))
    return "\n\n".join(blocks)


def resolve_citations(answer: str, nodes) -> Tuple[str, List[Dict], int]:
    """Map the answer's [n] markers to the cited pages.

    Pages are numbered in order of first citation, and the markers in the answer are rewritten
    to those numbers, so the answer and the source list shown to the user agree. Markers that
    point outside the retrieved sources are dropped and counted as invalid.

    Returns (answer with renumbered markers, cited sources, number of invalid markers).
    """
    answer = NATIVE_CITATION_PATTERN.sub(r"[\1]", answer)
    page_numbers: Dict[Tuple[str, str], int] = {}
    sources: List[Dict] = []
    invalid = 0

    def renumber(match: re.Match) -> str:
        nonlocal invalid
        numbers = []
        sentence = _citing_sentence(answer, match.start())
        for raw in re.findall(r"\d+", match.group(0)):
            index = int(raw) - 1
            if not 0 <= index < len(nodes):
                invalid += 1
                continue
            node = nodes[index]
            key = (node.metadata.get("file_name", ""), str(node.metadata.get("page_label", "")))
            highlight = pick_highlight(sentence, html.unescape(node.get_content()))
            if key not in page_numbers:
                page_numbers[key] = len(page_numbers) + 1
                title, year = document_title(key[0])
                sources.append({
                    "number": page_numbers[key],
                    "file_name": key[0],
                    "page": key[1],
                    "category": node.metadata.get("category", ""),
                    "title": title,
                    "year": year,
                    "search": highlight,
                })
            elif highlight and not sources[page_numbers[key] - 1]["search"]:
                # Another chunk of the same page may overlap the citing sentence better
                sources[page_numbers[key] - 1]["search"] = highlight
            if page_numbers[key] not in numbers:
                numbers.append(page_numbers[key])
        return "".join(f"[{n}]" for n in numbers)

    resolved = CITATION_PATTERN.sub(renumber, answer)
    return resolved, sources, invalid


def strip_citations(text: str) -> str:
    """Remove [n] markers, e.g. from earlier answers sent back as chat history"""
    return re.sub(r"[ \t]*" + CITATION_PATTERN.pattern, "", text)


def _citing_sentence(answer: str, position: int) -> str:
    """The sentence (or list item) that ends at a citation marker"""
    start = max(answer.rfind(".", 0, position), answer.rfind("\n", 0, position)) + 1
    return answer[start:position]


def pick_highlight(sentence: str, chunk_text: str):
    """A short phrase from the source chunk that best overlaps the citing sentence.

    Used as the PDF.js search term so the cited text gets highlighted. Best effort: when the
    chunk text differs from the PDF's own text layer, the viewer just opens the page.
    """
    sentence_words = {w.lower() for w in WORD_PATTERN.findall(sentence) if len(w) > 2 or w.isdigit()}
    words = list(WORD_PATTERN.finditer(chunk_text))
    if not sentence_words or len(words) < HIGHLIGHT_WORDS:
        return None
    best_score, best_start = 0, None
    for start in range(len(words) - HIGHLIGHT_WORDS + 1):
        window = words[start:start + HIGHLIGHT_WORDS]
        score = sum(1 for w in window if w.group(0).lower() in sentence_words)
        if score > best_score:
            best_score, best_start = score, start
    if best_start is None or best_score < 2:
        return None
    # Keep the original punctuation between the words (PDF.js phrase search needs it),
    # but drop markdown emphasis and line breaks
    phrase = chunk_text[words[best_start].start():words[best_start + HIGHLIGHT_WORDS - 1].end()]
    phrase = re.sub(r"-{3,}|[*_`#|]", " ", phrase)  # markdown emphasis and table rules
    return re.sub(r"\s+", " ", phrase).strip()
