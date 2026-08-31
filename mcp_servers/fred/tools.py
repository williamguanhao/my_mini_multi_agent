"""Pure-Python tool implementations for the FRED MCP server."""

import os

import pandas as pd
from fredapi import Fred
from mini_agent.config import FRED_API_KEY

def _client() -> Fred:
    api_key = FRED_API_KEY
    if not api_key:
        raise ValueError("FRED_API_KEY environment variable is not set")
    return Fred(api_key=api_key)


def get_series(series_id: str, start: str = "", end: str = "") -> str:
    """Return a text summary of a FRED economic series."""
    kwargs = {}
    if start:
        kwargs["observation_start"] = start
    if end:
        kwargs["observation_end"] = end
    s = _client().get_series(series_id, **kwargs)
    if s is None or s.empty:
        raise ValueError(f"No data for FRED series {series_id}")
    last_date = s.index[-1].strftime("%Y-%m-%d")
    last_value = float(s.iloc[-1].item() if hasattr(s.iloc[-1], "item") else s.iloc[-1])
    return f"{series_id}: {last_value} (as of {last_date})"


def search_series(query: str) -> str:
    """Search FRED for series matching `query`."""
    df = _client().search(query)
    if df is None or df.empty:
        return f"No FRED series match '{query}'."
    lines = [f"FRED series matching '{query}':"]
    for _, row in df.head(10).iterrows():
        lines.append(f"  {row['id']}: {row['title']}")
    return "\n".join(lines)