from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any

import yaml


CONFIG_DIR_NAME = ".paper_cli"
CONFIG_FILE_NAME = "config.yaml"
DEFAULT_SYSTEM_CONFIG_PATH = Path.home() / CONFIG_DIR_NAME / CONFIG_FILE_NAME

PROVIDER_OPENAI = "openai"
PROVIDER_CLAUDE = "claude"
PROVIDER_GEMINI = "gemini"
PROVIDER_DEEPSEEK = "deepseek"
PROVIDER_OTHERS = "others"

SUPPORTED_PROVIDERS = [
    PROVIDER_OPENAI,
    PROVIDER_CLAUDE,
    PROVIDER_GEMINI,
    PROVIDER_DEEPSEEK,
    PROVIDER_OTHERS,
]

PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    PROVIDER_OPENAI: {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-5",
        "api_key_env": "PAPERREADER_OPENAI_API_KEY",
    },
    PROVIDER_CLAUDE: {
        "base_url": "https://api.anthropic.com/v1/",
        "model": "claude-opus-4-6",
        "api_key_env": "PAPERREADER_CLAUDE_API_KEY",
    },
    PROVIDER_GEMINI: {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-3-flash-preview",
        "api_key_env": "PAPERREADER_GEMINI_API_KEY",
    },
    PROVIDER_DEEPSEEK: {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key_env": "PAPERREADER_DEEPSEEK_API_KEY",
    },
    PROVIDER_OTHERS: {
        "base_url": "",
        "model": "",
        "api_key_env": "PAPERREADER_OTHERS_API_KEY",
    },
}

DEFAULT_CONFIG_VALUES: dict[str, Any] = {
    "provider": PROVIDER_OPENAI,
    "provider_name": "",
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "model": "gpt-5",
    "system_prompt": "你是一个机器人，无人机领域的资深审稿人，精通的方向是视觉SLAM。请以严谨、清晰、可复现性导向的方式总结论文。",
    "max_chars": 120000,
    "chunk_chars": 12000,
    "recursive": True,
}


@dataclass(slots=True)
class AppConfig:
    provider: str
    provider_name: str
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


def provider_preset(provider: str) -> dict[str, str]:
    normalized = provider.strip().lower()
    if normalized == "third_party":
        normalized = PROVIDER_OTHERS
    if normalized not in PROVIDER_PRESETS:
        normalized = PROVIDER_OPENAI
    return PROVIDER_PRESETS[normalized]


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

    provider = str(raw.get("provider") or DEFAULT_CONFIG_VALUES["provider"]).strip().lower()
    if provider == "third_party":
        provider = PROVIDER_OTHERS
    if provider not in SUPPORTED_PROVIDERS:
        provider = PROVIDER_OPENAI

    provider_name = str(raw.get("provider_name") or "").strip()

    preset = provider_preset(provider)
    provider_key_env_name = preset["api_key_env"]

    env_base_url = os.getenv("PAPERREADER_BASE_URL")
    env_api_key = os.getenv("PAPERREADER_API_KEY")
    env_provider_api_key = os.getenv(provider_key_env_name)
    if provider == PROVIDER_OTHERS and not env_provider_api_key:
        env_provider_api_key = os.getenv("PAPERREADER_THIRD_PARTY_API_KEY")
    env_model = os.getenv("PAPERREADER_MODEL")
    env_system_prompt = os.getenv("PAPERREADER_SYSTEM_PROMPT")

    base_url = cli_base_url or env_base_url or raw.get("base_url") or preset["base_url"]
    api_key = cli_api_key or env_api_key or env_provider_api_key or raw.get("api_key") or ""
    model = cli_model or env_model or raw.get("model") or preset["model"]
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
        provider=provider,
        provider_name=provider_name,
        base_url=str(base_url).rstrip("/"),
        api_key=str(api_key),
        model=str(model),
        system_prompt=str(system_prompt),
        max_chars=max(2000, int(max_chars)),
        chunk_chars=max(1000, int(chunk_chars)),
        recursive=bool(recursive),
    )
