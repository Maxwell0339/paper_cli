from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .app import run_scan
from .config import (
    DEFAULT_CONFIG_VALUES,
    DEFAULT_SYSTEM_CONFIG_PATH,
    PROVIDER_PRESETS,
    SUPPORTED_PROVIDERS,
    load_config,
    provider_preset,
    write_config,
)

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
    preset = provider_preset(provider)

    base_url = typer.prompt("base_url", default=str(preset["base_url"] or DEFAULT_CONFIG_VALUES["base_url"]))
    console.print(
        f"[dim]Tip: You can also set API key via env {preset['api_key_env']} or PAPERREADER_API_KEY[/dim]"
    )
    api_key = typer.prompt("api_key", hide_input=True)
    model = typer.prompt("model", default=str(preset["model"] or DEFAULT_CONFIG_VALUES["model"]))
    system_prompt = typer.prompt(
        "system_prompt",
        default=str(DEFAULT_CONFIG_VALUES["system_prompt"]),
    )
    max_chars = typer.prompt("max_chars", default=int(DEFAULT_CONFIG_VALUES["max_chars"]), type=int)
    chunk_chars = typer.prompt("chunk_chars", default=int(DEFAULT_CONFIG_VALUES["chunk_chars"]), type=int)
    recursive = typer.confirm("recursive scan?", default=bool(DEFAULT_CONFIG_VALUES["recursive"]))

    values = {
        "provider": provider,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "system_prompt": system_prompt,
        "max_chars": max_chars,
        "chunk_chars": chunk_chars,
        "recursive": recursive,
    }
    write_config(config_path, values)
    console.print("[green]Config saved.[/green]")


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
        )
        report = run_scan(folder=folder_path, config=app_config, console=console)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[bold green]Done.[/bold green] total={report.total}, success={report.success}, failed={report.failed}"
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


if __name__ == "__main__":
    app()
