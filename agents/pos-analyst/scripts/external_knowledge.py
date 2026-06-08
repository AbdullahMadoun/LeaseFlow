"""Web-search adapter exposed to the agent as the `web_search` tool.

Intentionally narrow surface — the agent gets short, attributed snippets, not
raw HTML. Disabled by default; turn on via POS_WEB_SEARCH_ENABLED=true and
provide TAVILY_API_KEY (the default provider).

Per-job budget enforced by the agent loop itself (CONFIG.web_search_max_per_job).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import urllib.request
import urllib.error

from config import CONFIG

log = logging.getLogger("pos.web")


@dataclass
class WebSearchHit:
    title: str
    url: str
    snippet: str


@dataclass
class WebSearchResult:
    query: str
    hits: list[WebSearchHit]
    error: str | None = None

    def to_prompt(self) -> str:
        if self.error:
            return f"web_search error: {self.error}"
        if not self.hits:
            return f"web_search('{self.query}') returned no results."
        lines = [f"web_search results for: {self.query}", ""]
        for i, h in enumerate(self.hits, 1):
            lines.append(f"{i}. {h.title}")
            lines.append(f"   {h.url}")
            lines.append(f"   {h.snippet}")
            lines.append("")
        return "\n".join(lines)


def search(query: str, max_results: int = 5) -> WebSearchResult:
    if not CONFIG.web_search_enabled:
        return WebSearchResult(query=query, hits=[],
                               error="web_search is disabled (set POS_WEB_SEARCH_ENABLED=true)")
    if CONFIG.web_search_provider == "tavily":
        return _tavily(query, max_results)
    return WebSearchResult(query=query, hits=[],
                           error=f"unknown provider: {CONFIG.web_search_provider}")


def _tavily(query: str, max_results: int) -> WebSearchResult:
    if not CONFIG.web_search_api_key:
        return WebSearchResult(query=query, hits=[],
                               error="TAVILY_API_KEY not set")
    body = json.dumps({
        "api_key": CONFIG.web_search_api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return WebSearchResult(query=query, hits=[], error=f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        return WebSearchResult(query=query, hits=[], error=f"network: {e.reason}")
    except (TimeoutError, json.JSONDecodeError) as e:
        return WebSearchResult(query=query, hits=[], error=f"{type(e).__name__}: {e}")
    raw = payload.get("results") or []
    hits = [
        WebSearchHit(
            title=str(r.get("title", ""))[:200],
            url=str(r.get("url", "")),
            snippet=str(r.get("content", ""))[:600],
        )
        for r in raw[:max_results]
    ]
    return WebSearchResult(query=query, hits=hits)
