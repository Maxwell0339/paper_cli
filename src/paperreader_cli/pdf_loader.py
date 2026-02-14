from __future__ import annotations

from pathlib import Path
import re

import fitz


class PDFLoader:
    def __init__(self, max_chars: int = 120000) -> None:
        self.max_chars = max_chars

    def load_text(self, pdf_path: Path) -> tuple[str, bool]:
        try:
            doc = fitz.open(pdf_path)
        except Exception as exc:
            raise ValueError(f"Failed to open PDF: {pdf_path}") from exc

        pages: list[str] = []
        try:
            for page in doc:
                pages.append(page.get_text("text"))
        finally:
            doc.close()

        merged = "\n".join(pages)
        cleaned = self._clean_text(merged)
        truncated = len(cleaned) > self.max_chars
        if truncated:
            cleaned = cleaned[: self.max_chars]
        return cleaned, truncated

    @staticmethod
    def _clean_text(text: str) -> str:
        t = text.replace("\r\n", "\n").replace("\r", "\n")
        t = re.sub(r"[\t\f\v]+", " ", t)
        t = re.sub(r"(?<!\n)\n(?!\n)", " ", t)
        t = re.sub(r"\n{3,}", "\n\n", t)
        t = re.sub(r" {2,}", " ", t)
        return t.strip()
