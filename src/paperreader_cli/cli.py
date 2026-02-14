from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .app import run_scan
from .config import DEFAULT_SYSTEM_CONFIG_PATH, load_config

app = typer.Typer(
    help="PaperReader-CLI: batch read and summarize PDFs.",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main() -> None:
    """PaperReader-CLI root command group."""
    return None


@app.command()
def scan(
    folder_path: Path = typer.Argument(..., exists=True, file_okay=False, resolve_path=True),
    config: Path | None = typer.Option(None, "--config", help="Optional custom config path; default is ~/.paper_cli/config.yaml."),
    model: str | None = typer.Option(None, "--model", help="Override model."),
    base_url: str | None = typer.Option(None, "--base-url", help="Override API base_url."),
    api_key: str | None = typer.Option(None, "--api-key", help="Override API key."),
    system_prompt: str | None = typer.Option(None, "--system-prompt", help="Override system prompt."),
    max_chars: int | None = typer.Option(None, "--max-chars", help="Max chars per PDF before truncation."),
    chunk_chars: int | None = typer.Option(None, "--chunk-chars", help="Chunk size for long-context summarization."),
    recursive: bool | None = typer.Option(None, "--recursive/--no-recursive", help="Recursive scan switch."),
) -> None:
    """Scan a folder and summarize all PDF files."""
    try:
        target_config_path = config or DEFAULT_SYSTEM_CONFIG_PATH
        app_config = load_config(
            config_path=target_config_path,
            cli_base_url=base_url,
            cli_api_key=api_key,
            cli_model=model,
            cli_system_prompt=system_prompt,
            cli_max_chars=max_chars,
            cli_chunk_chars=chunk_chars,
            cli_recursive=recursive,
        )
        report = run_scan(folder=folder_path, config=app_config, console=console)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[bold green]Done.[/bold green] total={report.total}, success={report.success}, failed={report.failed}"
    )


if __name__ == "__main__":
    app()
