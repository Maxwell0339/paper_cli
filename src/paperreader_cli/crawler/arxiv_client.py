from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ARXIV_API_URL = "https://export.arxiv.org/api/query"
DEFAULT_USER_AGENT = "paperreader-cli/0.1 (+https://github.com/Maxwell0339/paper_cli)"


@dataclass(slots=True)
class ArxivPaper:
    arxiv_id: str
    title: str
    pdf_url: str


class ArxivClientError(RuntimeError):
    pass


def _text(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def _extract_id(raw_id: str) -> str:
    if not raw_id:
        return ""
    parts = raw_id.rstrip("/").split("/")
    return parts[-1]


def _extract_pdf_url(entry: ET.Element, arxiv_id: str, ns: dict[str, str]) -> str:
    for link in entry.findall("atom:link", ns):
        title = (link.attrib.get("title") or "").strip().lower()
        rel = (link.attrib.get("rel") or "").strip().lower()
        href = (link.attrib.get("href") or "").strip()
        if not href:
            continue
        if title == "pdf":
            return href
        if rel == "related" and href.endswith(".pdf"):
            return href

    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    raise ValueError("No valid pdf url found in arXiv entry")


def search_arxiv(
    query: str,
    max_results: int,
    sort_by: str = "submittedDate",
    sort_order: str = "descending",
    timeout: int = 30,
) -> list[ArxivPaper]:
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query cannot be empty")

    params = {
        "search_query": f"all:{normalized_query}",
        "start": 0,
        "max_results": max(1, int(max_results)),
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    url = f"{ARXIV_API_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ArxivClientError(f"Failed to query arXiv API: {exc}") from exc

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ArxivClientError("Invalid XML response from arXiv API") from exc
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    papers: list[ArxivPaper] = []
    for entry in root.findall("atom:entry", ns):
        raw_id = _text(entry.find("atom:id", ns))
        title = " ".join(_text(entry.find("atom:title", ns)).split())
        arxiv_id = _extract_id(raw_id)
        if not title:
            continue

        try:
            pdf_url = _extract_pdf_url(entry, arxiv_id, ns)
        except ValueError as exc:
            raise ArxivClientError(f"Invalid entry for arXiv id {arxiv_id or raw_id}") from exc
        papers.append(ArxivPaper(arxiv_id=arxiv_id, title=title, pdf_url=pdf_url))

    return papers


def download_pdf(pdf_url: str, target_path: Path, timeout: int = 60, chunk_size: int = 64 * 1024) -> None:
    request = Request(pdf_url, headers={"User-Agent": DEFAULT_USER_AGENT})
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with urlopen(request, timeout=timeout) as response:
            first_chunk = response.read(1024)
            if not first_chunk.startswith(b"%PDF"):
                raise ArxivClientError("Downloaded content is not a PDF")

            with target_path.open("wb") as file_obj:
                file_obj.write(first_chunk)
                for chunk in iter(lambda: response.read(chunk_size), b""):
                    file_obj.write(chunk)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        try:
            if target_path.exists():
                target_path.unlink()
        except OSError:
            pass
        raise ArxivClientError(f"Failed to download PDF from {pdf_url}: {exc}") from exc
