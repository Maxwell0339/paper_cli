from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel


def render_summary_saved(
    console: Console,
    *,
    pdf_name: str,
    output_path: Path,
    chunks_used: int,
    truncated: bool,
) -> None:
    trunc_note = " [yellow](truncated input)[/yellow]" if truncated else ""
    console.print(
        Panel.fit(
            f"[bold]{pdf_name}[/bold]{trunc_note}\n"
            f"Chunks used: {chunks_used}\n"
            f"Output: {output_path}",
            title="Summary Saved",
            border_style="green",
        )
    )
    if truncated:
        console.print("[yellow]Input exceeded max_chars; consider a longer-context model or larger --max-chars.[/yellow]")


def render_brief_markdown(console: Console, content: str, max_preview_chars: int = 2500) -> None:
    console.print(Markdown(content[:max_preview_chars]))
