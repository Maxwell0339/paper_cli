from __future__ import annotations

from pathlib import Path
import re

_MAX_FILENAME_LENGTH = 180
_INVALID_CHARS = re.compile(r"[\\/:*?\"<>|]+")
_WHITESPACE = re.compile(r"\s+")


def normalize_title_to_filename(title: str) -> str:
    cleaned = _INVALID_CHARS.sub(" ", title)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip().strip(".")
    if not cleaned:
        cleaned = "untitled"
    if len(cleaned) > _MAX_FILENAME_LENGTH:
        cleaned = cleaned[:_MAX_FILENAME_LENGTH].rstrip()
    return f"{cleaned}.pdf"


def resolve_output_dir(path_str: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path
