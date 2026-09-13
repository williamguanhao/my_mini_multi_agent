"""Pure-Python tool implementations for the websearch MCP server."""

from ddgs import DDGS
from ddgs.exceptions import DDGSException


def web_search(query: str, max_results: int = 5) -> str:
    """Run a web search and return a text summary of top results.

    Uses the `ddgs` metasearch package (DuckDuckGo + fallback engines);
    no API key required.
    """
    n = max(1, min(int(max_results), 20))

    try:
        results = list(DDGS().text(query, max_results=n))
    except DDGSException as e:
        return (
            f"Web search failed for '{query}': {e}. "
            "Try rephrasing the query or retrying shortly."
        )

    if not results:
        return f"No results for '{query}'."

    lines = [f"Search results for '{query}':"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        href = r.get("href", "")
        body = r.get("body", "").strip()
        lines.append(f"  {i}. {title}")
        if href:
            lines.append(f"     {href}")
        if body:
            lines.append(f"     {body}")
    return "\n".join(lines)
