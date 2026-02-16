from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from .cache import CacheEntry, SummaryCache, build_summary_cache_key, file_sha256
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


@dataclass(slots=True)
class _FileProcessResult:
    pdf_name: str
    output_path: Path
    chunks_used: int
    truncated: bool
    total_tokens: int
    from_cache: bool


def run_scan(folder: Path, config: AppConfig, console: Console, summary_output_dir: Path) -> ProcessReport:
    pdfs = find_pdfs(folder, recursive=config.recursive)
    if not pdfs:
        console.print(f"[yellow]No PDF files found in {folder}[/yellow]")
        return ProcessReport(total=0, success=0, failed=0, total_tokens=0)

    if not config.api_key:
        raise ValueError("API key is empty. Set it in config.yaml, env, or CLI option.")

    console.print(
        "[cyan]Start scan[/cyan] "
        f"total_pdfs={len(pdfs)}, file_workers={config.file_workers}, "
        f"chunk_workers={config.chunk_workers}, cache={'on' if config.cache_enabled else 'off'}"
    )

    llm = LLMClient(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model,
        request_timeout=config.request_timeout,
        max_retries=config.max_retries,
        rate_limit_qps=config.rate_limit_qps,
    )

    cache = SummaryCache(summary_output_dir / ".summary_cache.json") if config.cache_enabled else None

    success = 0
    failed = 0
    total_tokens = 0

    def _process_one(pdf: Path) -> _FileProcessResult:
        loader = PDFLoader(max_chars=config.max_chars)
        text, truncated = loader.load_text(pdf)

        if cache is not None:
            pdf_hash = file_sha256(pdf)
            cache_key = build_summary_cache_key(
                pdf_hash=pdf_hash,
                model=config.model,
                system_prompt=config.system_prompt,
                max_chars=config.max_chars,
                chunk_chars=config.chunk_chars,
                profile=config.profile,
            )
            cached = cache.get(cache_key)
            if cached is not None:
                output_path = write_markdown_for_pdf(pdf, cached.content, summary_output_dir)
                return _FileProcessResult(
                    pdf_name=pdf.name,
                    output_path=output_path,
                    chunks_used=cached.chunks_used,
                    truncated=cached.truncated,
                    total_tokens=0,
                    from_cache=True,
                )

        summary = summarize_paper(
            llm,
            system_prompt=config.system_prompt,
            paper_text=text,
            chunk_chars=config.chunk_chars,
            chunk_workers=config.chunk_workers,
            profile=config.profile,
        )
        output_path = write_markdown_for_pdf(pdf, summary.content, summary_output_dir)

        if cache is not None:
            cache.set(
                cache_key,
                CacheEntry(
                    content=summary.content,
                    chunks_used=summary.chunks_used,
                    truncated=truncated,
                ),
            )

        return _FileProcessResult(
            pdf_name=pdf.name,
            output_path=output_path,
            chunks_used=summary.chunks_used,
            truncated=truncated,
            total_tokens=summary.total_tokens,
            from_cache=False,
        )

    max_workers = min(max(1, config.file_workers), len(pdfs))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_pdf = {
            executor.submit(_process_one, pdf): pdf for pdf in pdfs
        }
        processed = 0
        for future in as_completed(future_to_pdf):
            pdf = future_to_pdf[future]
            try:
                result = future.result()
            except (ValueError, LLMClientError) as exc:
                failed += 1
                processed += 1
                console.print(f"[red]Failed:[/red] {pdf} -> {exc}")
                console.print(f"[dim]Progress: {processed}/{len(pdfs)}[/dim]")
                continue
            except Exception as exc:
                failed += 1
                processed += 1
                console.print(f"[red]Failed:[/red] {pdf} -> unexpected error: {exc}")
                console.print(f"[dim]Progress: {processed}/{len(pdfs)}[/dim]")
                continue

            success += 1
            total_tokens += result.total_tokens
            processed += 1
            render_summary_saved(
                console,
                pdf_name=result.pdf_name,
                output_path=result.output_path,
                chunks_used=result.chunks_used,
                truncated=result.truncated,
                from_cache=result.from_cache,
            )
            console.print(f"[dim]Progress: {processed}/{len(pdfs)}[/dim]")

    return ProcessReport(total=len(pdfs), success=success, failed=failed, total_tokens=total_tokens)
