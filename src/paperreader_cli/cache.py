from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import logging
from pathlib import Path
import threading
import time
from typing import Any


@dataclass(slots=True)
class CacheEntry:
    content: str
    chunks_used: int
    truncated: bool


LOGGER = logging.getLogger(__name__)


def file_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


class SummaryCache:
    def __init__(self, path: Path, max_entries: int = 500) -> None:
        self.path = path
        self.max_entries = max(50, int(max_entries))
        self._lock = threading.Lock()
        self._entries: dict[str, dict[str, Any]] = {}
        self._hash_by_fingerprint: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._entries = {}
            self._hash_by_fingerprint = {}
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("entries"), dict):
                self._entries = loaded["entries"]
                hash_map = loaded.get("hash_by_fingerprint")
                self._hash_by_fingerprint = hash_map if isinstance(hash_map, dict) else {}
            elif isinstance(loaded, dict):
                self._entries = loaded
                self._hash_by_fingerprint = {}
            else:
                self._entries = {}
                self._hash_by_fingerprint = {}
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("Failed to load summary cache at %s: %s", self.path, exc)
            self._entries = {}
            self._hash_by_fingerprint = {}

        self._prune_entries_locked()
        self._prune_hash_map_locked()

    def _prune_entries_locked(self) -> None:
        overflow = len(self._entries) - self.max_entries
        if overflow <= 0:
            return

        ordered_keys = sorted(
            self._entries,
            key=lambda key: float(self._entries[key].get("updated_at") or 0.0),
        )
        for key in ordered_keys[:overflow]:
            self._entries.pop(key, None)

    def _prune_hash_map_locked(self) -> None:
        max_hash_entries = self.max_entries * 4
        overflow = len(self._hash_by_fingerprint) - max_hash_entries
        if overflow <= 0:
            return

        ordered_keys = sorted(self._hash_by_fingerprint)
        for key in ordered_keys[:overflow]:
            self._hash_by_fingerprint.pop(key, None)

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = {
            "entries": self._entries,
            "hash_by_fingerprint": self._hash_by_fingerprint,
        }
        tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, key: str) -> CacheEntry | None:
        with self._lock:
            raw = self._entries.get(key)
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
            self._entries[key] = {
                "content": entry.content,
                "chunks_used": entry.chunks_used,
                "truncated": entry.truncated,
                "updated_at": time.time(),
            }
            self._prune_entries_locked()
            self._persist()

    def get_cached_file_hash(self, path: Path) -> str | None:
        with self._lock:
            return self._hash_by_fingerprint.get(file_fingerprint(path))

    def remember_file_hash(self, path: Path, pdf_hash: str) -> None:
        with self._lock:
            self._hash_by_fingerprint[file_fingerprint(path)] = pdf_hash
            self._prune_hash_map_locked()
            self._persist()

    def resolve_file_hash(self, path: Path) -> str:
        cached_hash = self.get_cached_file_hash(path)
        if cached_hash:
            return cached_hash

        resolved = file_sha256(path)
        self.remember_file_hash(path, resolved)
        return resolved


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
