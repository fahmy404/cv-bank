"""Utility helpers for the CV bank CLI."""
from __future__ import annotations

from typing import Iterable, List, Optional

from .db import Candidate


def parse_skills(comma_separated: Optional[str], repeated_flags: Optional[Iterable[str]]) -> List[str]:
    """Merge skills coming from different CLI options."""

    result: List[str] = []
    if comma_separated:
        result.extend(token.strip() for token in comma_separated.split(","))
    if repeated_flags:
        result.extend(repeated_flags)
    return [skill for skill in (skill.strip() for skill in result) if skill]


def format_candidate(candidate: Candidate, *, detailed: bool = False) -> str:
    """Convert a candidate object into a human readable string."""

    lines = [f"ID: {candidate.id}", f"Name: {candidate.name}"]
    if candidate.email:
        lines.append(f"Email: {candidate.email}")
    if candidate.phone:
        lines.append(f"Phone: {candidate.phone}")
    if candidate.job_title:
        lines.append(f"Job title: {candidate.job_title}")
    if candidate.company:
        lines.append(f"Company: {candidate.company}")
    if candidate.location:
        lines.append(f"Location: {candidate.location}")
    if candidate.skills:
        lines.append("Skills: " + ", ".join(candidate.skills))
    lines.append(f"Created: {candidate.created_at}")
    if candidate.file_name:
        lines.append(f"Stored file: {candidate.file_name}")
    if detailed and candidate.notes:
        lines.append("")
        lines.append("Notes:")
        lines.append(candidate.notes)
    if detailed and candidate.cv_text:
        lines.append("")
        lines.append("Extracted text snippet:")
        snippet = candidate.cv_text.strip().splitlines()
        preview = "\n".join(snippet[:10])
        lines.append(preview)
    return "\n".join(lines)


__all__ = ["parse_skills", "format_candidate"]
