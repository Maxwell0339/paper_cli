from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .arxiv_client import ArxivClientError, ArxivPaper, download_pdf, search_arxiv
from .storage import normalize_title_to_filename, resolve_output_dir


@dataclass(slots=True)
class CrawlReport:
    fetched: int = 0
    saved: int = 0
    skipped: int = 0
    failed: int = 0


def resolve_query(cli_query: str | None, last_query: str) -> str:
    query = (cli_query or "").strip()
    if query:
        return query

    fallback = (last_query or "").strip()
    if fallback:
        return fallback

    raise ValueError("Missing query. Use --query at least once before using fallback.")


def run_crawl(
    query: str,
    max_results: int,
    output_dir: Path,
    on_progress: Callable[[str, ArxivPaper, Path], None] | None = None,
) -> CrawlReport:
    papers = search_arxiv(query=query, max_results=max_results)
    report = CrawlReport(fetched=len(papers))

    for paper in papers:
        filename = normalize_title_to_filename(paper.title)
        target_path = output_dir / filename

        if target_path.exists():
            report.skipped += 1
            if on_progress:
                on_progress("skip", paper, target_path)
            continue

        try:
            download_pdf(paper.pdf_url, target_path)
            report.saved += 1
            if on_progress:
                on_progress("saved", paper, target_path)
        except (ArxivClientError, OSError, ValueError):
            report.failed += 1
            if on_progress:
                on_progress("failed", paper, target_path)

    return report


def prepare_output_dir(cli_output_dir: str | None, default_output_dir: str) -> Path:
    selected = (cli_output_dir or "").strip() or default_output_dir
    return resolve_output_dir(selected)
