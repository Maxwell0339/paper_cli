from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from .config import AppConfig
from .llm_client import LLMClient, LLMClientError
from .pdf_loader import PDFLoader
from .renderer import render_summary_saved
from .scanner import find_pdfs
from .summarizer import summarize_paper
from .writer import write_markdown_for_pdf


@dataclass(slots=True)
class ProcessReport:
    total: int
    success: int
    failed: int
    total_tokens: int


def run_scan(folder: Path, config: AppConfig, console: Console, summary_output_dir: Path) -> ProcessReport:
    pdfs = find_pdfs(folder, recursive=config.recursive)
    if not pdfs:
        console.print(f"[yellow]No PDF files found in {folder}[/yellow]")
        return ProcessReport(total=0, success=0, failed=0, total_tokens=0)

    if not config.api_key:
        raise ValueError("API key is empty. Set it in config.yaml, env, or CLI option.")

    llm = LLMClient(api_key=config.api_key, base_url=config.base_url, model=config.model)
    loader = PDFLoader(max_chars=config.max_chars)

    success = 0
    failed = 0
    total_tokens = 0

    for pdf in pdfs:
        with console.status(f"[bold cyan]Processing[/bold cyan] {pdf.name} ...", spinner="dots"):
            try:
                text, truncated = loader.load_text(pdf)
                summary = summarize_paper(
                    llm,
                    system_prompt=config.system_prompt,
                    paper_text=text,
                    chunk_chars=config.chunk_chars,
                )
                output_path = write_markdown_for_pdf(pdf, summary.content, summary_output_dir)
            except (ValueError, LLMClientError) as exc:
                failed += 1
                console.print(f"[red]Failed:[/red] {pdf} -> {exc}")
                continue

        success += 1
        total_tokens += summary.total_tokens
        render_summary_saved(
            console,
            pdf_name=pdf.name,
            output_path=output_path,
            chunks_used=summary.chunks_used,
            truncated=truncated,
        )

    return ProcessReport(total=len(pdfs), success=success, failed=failed, total_tokens=total_tokens)
