"""Helpers for extracting text from CV files."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional


def extract_text_from_file(file_path: Path) -> Optional[str]:
    """Best-effort text extraction from a CV file."""

    extractor = _choose_extractor(file_path)
    if extractor is None:
        return None
    return extractor(file_path)


def _choose_extractor(file_path: Path) -> Optional[Callable[[Path], str]]:
    suffix = file_path.suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json"}:
        return _read_plain_text
    if suffix == ".pdf":
        return _read_pdf
    if suffix == ".docx":
        return _read_docx
    return None


def _read_plain_text(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def _read_pdf(file_path: Path) -> str:
    try:
        from PyPDF2 import PdfReader  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Reading PDF files requires the optional PyPDF2 package. "
            "Install it with 'pip install PyPDF2' or provide --text-source."
        ) from exc

    reader = PdfReader(str(file_path))
    contents = []
    for page in reader.pages:
        text = page.extract_text() or ""
        contents.append(text)
    return "\n".join(contents)


def _read_docx(file_path: Path) -> str:
    try:
        import docx  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Reading DOCX files requires the optional python-docx package. "
            "Install it with 'pip install python-docx' or provide --text-source."
        ) from exc

    document = docx.Document(str(file_path))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


__all__ = ["extract_text_from_file"]
