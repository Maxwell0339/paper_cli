from __future__ import annotations

from pathlib import Path


def write_markdown_next_to_pdf(pdf_path: Path, markdown_content: str) -> Path:
    output_path = pdf_path.with_suffix(".md")
    output_path.write_text(markdown_content, encoding="utf-8")
    return output_path
