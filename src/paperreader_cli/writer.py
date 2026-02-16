from __future__ import annotations

from pathlib import Path


def write_markdown_for_pdf(pdf_path: Path, markdown_content: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{pdf_path.stem}.md"
    output_path.write_text(markdown_content, encoding="utf-8")
    return output_path
