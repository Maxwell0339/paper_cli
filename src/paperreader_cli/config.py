from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any

import yaml


CONFIG_DIR_NAME = ".paper_cli"
CONFIG_FILE_NAME = "config.yaml"
DEFAULT_SYSTEM_CONFIG_PATH = Path.home() / CONFIG_DIR_NAME / CONFIG_FILE_NAME

DEFAULT_CONFIG_VALUES: dict[str, Any] = {
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "model": "gpt-4o-mini",
    "system_prompt": "你是一个计算机视觉领域的资深审稿人。请以严谨、清晰、可复现性导向的方式总结论文。",
    "max_chars": 120000,
    "chunk_chars": 12000,
    "recursive": True,
}


@dataclass(slots=True)
class AppConfig:
    base_url: str
    api_key: str
    model: str
    system_prompt: str
    max_chars: int = 120000
    chunk_chars: int = 12000
    recursive: bool = True


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in config file: {path}") from exc

    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping")
    return data


def write_config(config_path: Path, values: dict[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(values, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def load_config(
    config_path: Path | None = None,
    cli_base_url: str | None = None,
    cli_api_key: str | None = None,
    cli_model: str | None = None,
    cli_system_prompt: str | None = None,
    cli_max_chars: int | None = None,
    cli_chunk_chars: int | None = None,
    cli_recursive: bool | None = None,
) -> AppConfig:
    config_path = config_path or DEFAULT_SYSTEM_CONFIG_PATH
    raw = _read_yaml(config_path)

    env_base_url = os.getenv("PAPERREADER_BASE_URL")
    env_api_key = os.getenv("PAPERREADER_API_KEY")
    env_model = os.getenv("PAPERREADER_MODEL")
    env_system_prompt = os.getenv("PAPERREADER_SYSTEM_PROMPT")

    base_url = cli_base_url or env_base_url or raw.get("base_url") or "https://api.openai.com/v1"
    api_key = cli_api_key or env_api_key or raw.get("api_key") or ""
    model = cli_model or env_model or raw.get("model") or "gpt-4o-mini"
    system_prompt = (
        cli_system_prompt
        or env_system_prompt
        or raw.get("system_prompt")
        or "你是一位严谨的学术审稿人，请结构化总结论文。"
    )

    max_chars = cli_max_chars if cli_max_chars is not None else int(raw.get("max_chars", 120000))
    chunk_chars = cli_chunk_chars if cli_chunk_chars is not None else int(raw.get("chunk_chars", 12000))
    recursive = cli_recursive if cli_recursive is not None else bool(raw.get("recursive", True))

    return AppConfig(
        base_url=str(base_url).rstrip("/"),
        api_key=str(api_key),
        model=str(model),
        system_prompt=str(system_prompt),
        max_chars=max(2000, int(max_chars)),
        chunk_chars=max(1000, int(chunk_chars)),
        recursive=bool(recursive),
    )
