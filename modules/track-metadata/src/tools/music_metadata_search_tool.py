from __future__ import annotations

from typing import Any, ClassVar, Optional
from urllib.parse import urlparse

from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import BaseTool


class MusicMetadataSearchTool(BaseTool):
    """Custom Tavily wrapper focused on key music metadata sources."""

    name: str = "MusicMetadataSearch"
    description: str = (
        "Search Beatport, SoundCloud, Discogs, Bandcamp, Apple Music, Amazon Music, "
        "Hypeddit, and the open web for track metadata. "
        "Returns aggregated textual snippets that may contain title, artist, album, label, genre, "
        "remixer, year, tempo, and key information."
    )
    _source_domains: ClassVar[dict[str, str]] = {
        "Beatport": "beatport.com",
        "SoundCloud": "soundcloud.com",
        "Discogs": "discogs.com",
        "Bandcamp": "bandcamp.com",
        "Apple Music": "music.apple.com",
        "Amazon Music": "music.amazon.com",
        "Hypeddit": "hypeddit.com",
    }

    def __init__(self, tavily_tool: TavilySearchResults, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._tavily_tool = tavily_tool

    def _run(self, query: str, run_manager: Optional[Any] = None) -> str:
        _ = run_manager
        try:
            cleaned_results, raw_results = self._tavily_tool._run(query=query)
        except Exception as exc:  # pragma: no cover - external API behaviour
            return f"Error performing search: {exc}"

        if isinstance(cleaned_results, str):
            return cleaned_results

        domain_sections: dict[str, list[str]] = {label: [] for label in self._source_domains}
        general_hits: list[str] = []

        iterable_results: list[dict[str, Any]] = []
        if isinstance(cleaned_results, list):
            iterable_results = [item for item in cleaned_results if isinstance(item, dict)]
        elif isinstance(raw_results, dict):
            iterable_results = [
                item for item in raw_results.get("results", []) if isinstance(item, dict)
            ]

        for item in iterable_results:
            snippet = self._format_result(item)
            if not snippet:
                continue
            matched_label = self._match_domain(item.get("url", ""))
            if matched_label:
                domain_sections[matched_label].append(snippet)
            else:
                general_hits.append(snippet)

        sections: list[str] = []
        for label, entries in domain_sections.items():
            if entries:
                sections.append(f"[{label}]\n\n" + "\n\n".join(entries))

        if general_hits:
            sections.append("[Open Web]\n\n" + "\n\n".join(general_hits))

        if isinstance(raw_results, dict):
            answer = raw_results.get("answer")
            if answer:
                sections.append(f"[Summary]\n{answer}")

        if not sections and isinstance(raw_results, dict):
            fallback_entries: list[str] = []
            for item in raw_results.get("results", []):
                if not isinstance(item, dict):
                    continue
                formatted = self._format_result(item)
                if formatted:
                    fallback_entries.append(formatted)
            if fallback_entries:
                sections.append("[Open Web]\n\n" + "\n\n".join(fallback_entries))

        if not sections:
            sections.append("No results returned.")

        return "\n\n".join(sections)

    def _match_domain(self, url: str | None) -> str | None:
        if not url:
            return None
        domain = urlparse(url).netloc.lower()
        for label, needle in self._source_domains.items():
            if domain.endswith(needle):
                return label
        return None

    def _format_result(self, item: dict[str, Any]) -> str:
        parts: list[str] = []
        title = item.get("title")
        content = item.get("content")
        url = item.get("url")
        if isinstance(title, str) and title.strip():
            parts.append(title.strip())
        if isinstance(content, str) and content.strip():
            parts.append(content.strip())
        if isinstance(url, str) and url.strip():
            parts.append(url.strip())
        return "\n".join(parts).strip()

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        raise NotImplementedError("MusicMetadataSearchTool does not support async usage.")


__all__ = ["MusicMetadataSearchTool"]
