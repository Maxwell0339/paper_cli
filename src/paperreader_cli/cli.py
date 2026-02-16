from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .app import run_scan
from .config import (
    DEFAULT_SCAN_FOLDER,
    DEFAULT_SUMMARY_OUTPUT_DIR,
    DEFAULT_CONFIG_VALUES,
    DEFAULT_SYSTEM_CONFIG_PATH,
    PROVIDER_OTHERS,
    SUPPORTED_PROVIDERS,
    load_config,
    provider_preset,
    read_config_values,
    update_config_values,
    write_config,
)
from .crawler.service import prepare_output_dir, resolve_query, run_crawl

app = typer.Typer(
    help="PaperReader-CLI: batch read and summarize PDFs.",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main() -> None:
    """PaperReader-CLI root command group."""
    return None


def _bootstrap_config_interactive(config_path: Path) -> None:
    console.print(f"[cyan]First-time setup:[/cyan] creating config at {config_path}")

    console.print("[bold]Select provider:[/bold]")
    for idx, name in enumerate(SUPPORTED_PROVIDERS, start=1):
        console.print(f"  {idx}. {name}")
    provider_index = typer.prompt("provider index", default=1, type=int)
    if provider_index < 1 or provider_index > len(SUPPORTED_PROVIDERS):
        provider_index = 1
    provider = SUPPORTED_PROVIDERS[provider_index - 1]
    provider_name = ""
    if provider == PROVIDER_OTHERS:
        provider_name = typer.prompt("provider_name (manual)").strip()
        if not provider_name:
            raise typer.BadParameter("provider_name is required when provider=others")

    preset = provider_preset(provider)

    base_url = typer.prompt("base_url", default=str(preset["base_url"] or DEFAULT_CONFIG_VALUES["base_url"]))
    console.print(
        f"[dim]Tip: You can also set API key via env {preset['api_key_env']} or PAPERREADER_API_KEY[/dim]"
    )
    api_key = typer.prompt("api_key", hide_input=False)
    model = typer.prompt("model", default=str(preset["model"] or DEFAULT_CONFIG_VALUES["model"]))
    system_prompt = typer.prompt(
        "system_prompt",
        default=str(DEFAULT_CONFIG_VALUES["system_prompt"]),
    )
    max_chars = typer.prompt("max_chars", default=int(DEFAULT_CONFIG_VALUES["max_chars"]), type=int)
    chunk_chars = typer.prompt("chunk_chars", default=int(DEFAULT_CONFIG_VALUES["chunk_chars"]), type=int)
    recursive = typer.confirm("recursive scan?", default=bool(DEFAULT_CONFIG_VALUES["recursive"]))
    file_workers = typer.prompt("file_workers", default=int(DEFAULT_CONFIG_VALUES["file_workers"]), type=int)
    chunk_workers = typer.prompt("chunk_workers", default=int(DEFAULT_CONFIG_VALUES["chunk_workers"]), type=int)
    request_timeout = typer.prompt("request_timeout", default=int(DEFAULT_CONFIG_VALUES["request_timeout"]), type=int)
    max_retries = typer.prompt("max_retries", default=int(DEFAULT_CONFIG_VALUES["max_retries"]), type=int)
    rate_limit_qps = typer.prompt("rate_limit_qps", default=float(DEFAULT_CONFIG_VALUES["rate_limit_qps"]), type=float)
    cache_enabled = typer.confirm("enable cache?", default=bool(DEFAULT_CONFIG_VALUES["cache_enabled"]))
    profile = typer.prompt("profile (paper/report)", default=str(DEFAULT_CONFIG_VALUES["profile"]))
    default_scan_folder = typer.prompt("default_scan_folder", default=str(DEFAULT_SCAN_FOLDER))
    default_summary_output_dir = typer.prompt("default_summary_output_dir", default=str(DEFAULT_SUMMARY_OUTPUT_DIR))

    values = {
        "provider": provider,
        "provider_name": provider_name,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "system_prompt": system_prompt,
        "max_chars": max_chars,
        "chunk_chars": chunk_chars,
        "recursive": recursive,
        "file_workers": file_workers,
        "chunk_workers": chunk_workers,
        "request_timeout": request_timeout,
        "max_retries": max_retries,
        "rate_limit_qps": rate_limit_qps,
        "cache_enabled": cache_enabled,
        "profile": profile,
        "default_scan_folder": default_scan_folder,
        "default_summary_output_dir": default_summary_output_dir,
    }
    write_config(config_path, values)
    console.print("[green]Config saved.[/green]")


@app.command()
def scan(
    folder_path: Path | None = typer.Argument(None, exists=False, file_okay=False, resolve_path=True),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Summary markdown output directory; default is ~/.paper_cli/summary."),
    config: Path | None = typer.Option(None, "--config", help="Optional custom config path; default is ~/.paper_cli/config.yaml."),
    model: str | None = typer.Option(None, "--model", help="Override model."),
    base_url: str | None = typer.Option(None, "--base-url", help="Override API base_url."),
    api_key: str | None = typer.Option(None, "--api-key", help="Override API key."),
    system_prompt: str | None = typer.Option(None, "--system-prompt", help="Override system prompt."),
    max_chars: int | None = typer.Option(None, "--max-chars", help="Max chars per PDF before truncation."),
    chunk_chars: int | None = typer.Option(None, "--chunk-chars", help="Chunk size for long-context summarization."),
    recursive: bool | None = typer.Option(None, "--recursive/--no-recursive", help="Recursive scan switch."),
    file_workers: int | None = typer.Option(None, "--file-workers", min=1, help="Max concurrent PDF files being summarized."),
    chunk_workers: int | None = typer.Option(None, "--chunk-workers", min=1, help="Max concurrent chunks for one long PDF."),
    request_timeout: int | None = typer.Option(None, "--request-timeout", min=10, help="Per-request timeout in seconds."),
    max_retries: int | None = typer.Option(None, "--max-retries", min=0, help="Retry times for transient LLM errors."),
    rate_limit_qps: float | None = typer.Option(None, "--rate-limit-qps", min=0.1, help="Client-side max LLM requests per second."),
    cache_enabled: bool | None = typer.Option(None, "--cache/--no-cache", help="Enable summary cache by PDF hash + config fingerprint."),
    profile: str | None = typer.Option(None, "--profile", help="Summarization profile: paper or report."),
) -> None:
    """Scan a folder and summarize all PDF files."""
    try:
        target_config_path = config or DEFAULT_SYSTEM_CONFIG_PATH
        if not target_config_path.exists():
            _bootstrap_config_interactive(target_config_path)

        app_config = load_config(
            config_path=target_config_path,
            cli_base_url=base_url,
            cli_api_key=api_key,
            cli_model=model,
            cli_system_prompt=system_prompt,
            cli_max_chars=max_chars,
            cli_chunk_chars=chunk_chars,
            cli_recursive=recursive,
            cli_file_workers=file_workers,
            cli_chunk_workers=chunk_workers,
            cli_request_timeout=request_timeout,
            cli_max_retries=max_retries,
            cli_rate_limit_qps=rate_limit_qps,
            cli_cache_enabled=cache_enabled,
            cli_profile=profile,
        )
        final_folder = (folder_path or Path(app_config.default_scan_folder)).expanduser().resolve()
        final_output_dir = (output_dir or Path(app_config.default_summary_output_dir)).expanduser().resolve()

        if not final_folder.exists() or not final_folder.is_dir():
            raise NotADirectoryError(f"Invalid folder: {final_folder}")

        report = run_scan(
            folder=final_folder,
            config=app_config,
            console=console,
            summary_output_dir=final_output_dir,
        )
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[bold green]Done.[/bold green] total={report.total}, success={report.success}, failed={report.failed}, total_tokens={report.total_tokens}"
    )


@app.command("reconfigure")
def reconfigure(
    config: Path | None = typer.Option(None, "--config", help="Optional custom config path; default is ~/.paper_cli/config.yaml."),
) -> None:
    """One-click: rerun interactive config wizard and overwrite existing config."""
    try:
        target_config_path = config or DEFAULT_SYSTEM_CONFIG_PATH
        _bootstrap_config_interactive(target_config_path)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("crawl")
def crawl(
    query: str | None = typer.Option(None, "--query", "-q", help="ArXiv search query; fallback to last used query if omitted."),
    max_results: int = typer.Option(10, "--max-results", "-n", min=1, help="Max number of papers to fetch from ArXiv."),
    output_dir: str | None = typer.Option(None, "--output-dir", help="Override PDF output directory; default follows default_scan_folder (~/.paper_cli/papers)."),
    config: Path | None = typer.Option(None, "--config", help="Optional custom config path; default is ~/.paper_cli/config.yaml."),
) -> None:
    """Fetch papers from ArXiv by keyword and save PDFs."""
    try:
        target_config_path = config or DEFAULT_SYSTEM_CONFIG_PATH
        values = read_config_values(target_config_path)

        final_query = resolve_query(query, str(values.get("last_crawl_query") or ""))
        configured_papers_dir = str(
            values.get("default_scan_folder")
            or values.get("default_crawl_output_dir")
            or ""
        )
        final_output_dir = prepare_output_dir(output_dir, configured_papers_dir)

        console.print(
            f"[cyan]Crawling ArXiv[/cyan] query='{final_query}', max_results={max_results}, output='{final_output_dir}'"
        )

        def _progress(status: str, _paper: object, path: Path) -> None:
            if status == "saved":
                console.print(f"[green]saved[/green] {path.name}")
            elif status == "skip":
                console.print(f"[yellow]skipped[/yellow] {path.name}")
            else:
                console.print(f"[red]failed[/red] {path.name}")

        report = run_crawl(
            query=final_query,
            max_results=max_results,
            output_dir=final_output_dir,
            on_progress=_progress,
        )

        update_config_values(
            target_config_path,
            {
                "last_crawl_query": final_query,
                "default_scan_folder": str(final_output_dir),
                "default_crawl_output_dir": str(final_output_dir),
            },
        )
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        "[bold green]Crawl done.[/bold green] "
        f"fetched={report.fetched}, saved={report.saved}, skipped={report.skipped}, failed={report.failed}"
    )


if __name__ == "__main__":
    app()
