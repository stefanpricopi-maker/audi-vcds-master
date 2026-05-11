from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pypdf import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag import RAGIndex  # noqa: E402


load_dotenv()

MANUALS_DIR = Path(os.getenv("MANUALS_DIR", "./data/manuals")).resolve()
PUBLIC_NOTES_DIR = Path(os.getenv("PUBLIC_NOTES_DIR", "./knowledge/public")).resolve()
VECTORSTORE_DIR = Path(os.getenv("VECTORSTORE_DIR", "./data/vectorstore")).resolve()


def _chunk_text(text: str, *, chunk_size: int = 1400, overlap: int = 200) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    chunks: list[str] = []
    i = 0
    while i < len(text):
        chunk = text[i : i + chunk_size]
        chunks.append(chunk)
        i += max(1, chunk_size - overlap)
    return chunks


def _stable_id(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:32]


def main():
    if not MANUALS_DIR.exists():
        print(f"Manuals dir does not exist (ok): {MANUALS_DIR}")

    rag = RAGIndex(persist_dir=VECTORSTORE_DIR)

    pdfs = sorted([p for p in MANUALS_DIR.rglob("*.pdf") if p.is_file()]) if MANUALS_DIR.exists() else []
    md_notes = (
        sorted([p for p in PUBLIC_NOTES_DIR.rglob("*.md") if p.is_file()])
        if PUBLIC_NOTES_DIR.exists()
        else []
    )
    if not pdfs and not md_notes:
        raise SystemExit(
            f"No PDFs found under {MANUALS_DIR} and no markdown notes under {PUBLIC_NOTES_DIR}"
        )

    total_chunks = 0

    for pdf_path in pdfs:
        reader = PdfReader(str(pdf_path))
        for page_idx, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            for chunk_idx, chunk in enumerate(_chunk_text(text), start=1):
                doc_key = f"{pdf_path.relative_to(MANUALS_DIR)}|p{page_idx}|c{chunk_idx}"
                cid = _stable_id(doc_key)
                rag.add_texts(
                    ids=[cid],
                    texts=[chunk],
                    metadatas=[
                        {
                            "source": str(pdf_path.relative_to(MANUALS_DIR)),
                            "page": page_idx,
                            "chunk": chunk_idx,
                        }
                    ],
                )
                total_chunks += 1

        print(f"Indexed {pdf_path.name} ({len(reader.pages)} pages)")

    for md_path in md_notes:
        text = md_path.read_text(encoding="utf-8", errors="replace")
        for chunk_idx, chunk in enumerate(_chunk_text(text), start=1):
            doc_key = f"{md_path.relative_to(PUBLIC_NOTES_DIR)}|c{chunk_idx}"
            cid = _stable_id(doc_key)
            rag.add_texts(
                ids=[cid],
                texts=[chunk],
                metadatas=[
                    {
                        "source": str(md_path.relative_to(PUBLIC_NOTES_DIR)),
                        "chunk": chunk_idx,
                        "source_type": "public_note",
                    }
                ],
            )
            total_chunks += 1
        print(f"Indexed note {md_path.name}")

    print(f"Done. Added/updated ~{total_chunks} chunks into {VECTORSTORE_DIR}")


if __name__ == "__main__":
    main()

