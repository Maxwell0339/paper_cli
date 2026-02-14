from __future__ import annotations

from pathlib import Path


def find_pdfs(folder: Path, recursive: bool = True) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        raise NotADirectoryError(f"Invalid folder: {folder}")

    pattern = "**/*.pdf" if recursive else "*.pdf"
    files = sorted(p for p in folder.glob(pattern) if p.is_file())
    return files
