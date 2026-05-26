"""Week 3 — RAG over quarterly earnings PDFs.

Retrieval-Augmented Generation: before the LLM answers a question, retrieve the
most relevant passages from a corpus and feed them into the prompt as context.
The model answers FROM those passages — so it can cite sources and is far less
likely to hallucinate.

Pipeline:
  1. Extract text from earnings-call / annual-report PDFs.
  2. Chunk it (1000 chars, 200 overlap). WHY overlap: a fact split across a
     chunk boundary still lands whole inside at least one chunk.
  3. Embed each chunk with Gemini's embedding model.
  4. Persist the vectors + chunk texts to disk.
  5. query_rag(): embed the question, find the nearest chunks, return them.

FAISS is OPTIONAL. If it is installed, query uses a FAISS index; if not, a
NumPy brute-force cosine search is used instead — fine for a few thousand
chunks. FAISS wins at large scale.

Run (from week3/):  python -m llm.rag  /path/to/pdfs
"""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from typing import Any

from . import embed

logger = logging.getLogger(__name__)

# faiss is optional — see the module docstring. `Any`-typed so use sites
# don't flag on the `faiss = None` fallback (see llm/__init__.py).
faiss: Any
try:
    import faiss  # pyrefly: ignore[missing-import]  # pyright: ignore[reportMissingImports]
    _HAS_FAISS = True
except ImportError:
    faiss = None
    _HAS_FAISS = False

# pypdf is required only to BUILD the index (not to query it).
PdfReader: Any
try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

INDEX_DIR = Path(__file__).resolve().parent.parent / ".cache" / "rag_index"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


@dataclass
class Chunk:
    """One retrieved passage: its text, the PDF it came from, its similarity."""
    text: str
    source: str
    score: float = 0.0


def extract_pdf_text(path: Path) -> str:
    """Extract all text from one PDF."""
    if PdfReader is None:
        raise RuntimeError("pypdf is not installed — pip install -r requirements.txt")
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping fixed-size chunks."""
    text = " ".join(text.split())  # normalise whitespace
    chunks: list[str] = []
    start = 0
    step = max(1, size - overlap)
    while start < len(text):
        chunks.append(text[start:start + size])
        start += step
    return [c for c in chunks if c.strip()]


def build_index(pdf_dir: str | Path, index_dir: Path = INDEX_DIR) -> int:
    """Build (and persist) the RAG index from every PDF in `pdf_dir`.

    Returns:
        The number of chunks indexed.
    """
    pdf_dir = Path(pdf_dir)
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        raise RuntimeError(f"no PDFs found in {pdf_dir}")

    texts: list[str] = []
    sources: list[str] = []
    for pdf in pdfs:
        for chunk in chunk_text(extract_pdf_text(pdf)):
            texts.append(chunk)
            sources.append(pdf.name)
    logger.info("RAG: %d chunk(s) from %d PDF(s) — embedding...", len(texts), len(pdfs))

    vectors = np.array(embed(texts), dtype="float32")
    index_dir.mkdir(parents=True, exist_ok=True)
    np.save(index_dir / "vectors.npy", vectors)
    (index_dir / "chunks.json").write_text(
        json.dumps([{"text": t, "source": s} for t, s in zip(texts, sources)]),
        encoding="utf-8")
    logger.info("RAG: index saved to %s (%d chunks)", index_dir, len(texts))
    return len(texts)


def _normalise(matrix: np.ndarray) -> np.ndarray:
    """L2-normalise rows so a dot product equals cosine similarity."""
    return matrix / (np.linalg.norm(matrix, axis=-1, keepdims=True) + 1e-9)


def query_rag(question: str, top_k: int = 5, index_dir: Path = INDEX_DIR) -> list[Chunk]:
    """Return the `top_k` chunks most relevant to `question`.

    Raises:
        RuntimeError: if no index has been built yet.
    """
    index_dir = Path(index_dir)
    if not (index_dir / "vectors.npy").exists():
        raise RuntimeError(
            f"no RAG index at {index_dir} — run build_index(pdf_dir) first")

    vectors = np.load(index_dir / "vectors.npy")
    chunks = json.loads((index_dir / "chunks.json").read_text(encoding="utf-8"))
    query_vec = np.array(embed([question])[0], dtype="float32")

    normed = _normalise(vectors)
    query_normed = _normalise(query_vec)

    if _HAS_FAISS:
        # Inner product on L2-normalised vectors == cosine similarity.
        # pyrefly: ignore[missing-attribute] -- guarded by _HAS_FAISS above
        index = faiss.IndexFlatIP(normed.shape[1])
        index.add(normed.astype("float32"))
        scores, idx = index.search(query_normed.reshape(1, -1).astype("float32"), top_k)
        idx, scores = idx[0], scores[0]
    else:
        logger.warning("RAG: faiss not installed — using NumPy brute-force search")
        sims = normed @ query_normed
        idx = np.argsort(sims)[::-1][:top_k]
        scores = sims[idx]

    results = [Chunk(text=chunks[i]["text"], source=chunks[i]["source"],
                     score=round(float(s), 4))
               for i, s in zip(idx, scores) if i < len(chunks)]
    logger.info("query_rag: '%s' -> %d chunk(s), top score %.3f",
                question[:50], len(results), results[0].score if results else 0.0)
    return results


if __name__ == "__main__":  # demo — needs GEMINI_API_KEY (+ pypdf to build)
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
    if len(sys.argv) < 2:
        print("Usage: python -m llm.rag /path/to/folder-of-earnings-pdfs")
        sys.exit(1)
    try:
        n = build_index(sys.argv[1])
        print(f"Indexed {n} chunks. Sample query:")
        for chunk in query_rag("What did management say about revenue growth?", top_k=3):
            print(f"  [{chunk.score}] {chunk.source}: {chunk.text[:120]}...")
    except RuntimeError as e:
        print(f"[skipped] {e}")
