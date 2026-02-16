from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import threading
from typing import Any


@dataclass(slots=True)
class CacheEntry:
    content: str
    chunks_used: int
    truncated: bool


class SummaryCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._data = {}
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self._data = loaded
            else:
                self._data = {}
        except Exception:
            self._data = {}

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, key: str) -> CacheEntry | None:
        with self._lock:
            raw = self._data.get(key)
            if not isinstance(raw, dict):
                return None
            content = raw.get("content")
            chunks_used = raw.get("chunks_used", 1)
            truncated = raw.get("truncated", False)
            if not isinstance(content, str):
                return None
            return CacheEntry(
                content=content,
                chunks_used=max(1, int(chunks_used)),
                truncated=bool(truncated),
            )

    def set(self, key: str, entry: CacheEntry) -> None:
        with self._lock:
            self._data[key] = {
                "content": entry.content,
                "chunks_used": entry.chunks_used,
                "truncated": entry.truncated,
            }
            self._persist()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_summary_cache_key(
    *,
    pdf_hash: str,
    model: str,
    system_prompt: str,
    max_chars: int,
    chunk_chars: int,
    profile: str,
) -> str:
    fingerprint = {
        "pdf_hash": pdf_hash,
        "model": model,
        "system_prompt": system_prompt,
        "max_chars": max_chars,
        "chunk_chars": chunk_chars,
        "profile": profile,
    }
    text = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True)
    return sha256(text.encode("utf-8")).hexdigest()
