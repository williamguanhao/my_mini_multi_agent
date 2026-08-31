"""Pure-Python tool implementations for the yfinance MCP server.

These functions take simple Python inputs and return strings. They know
nothing about MCP — the server.py module wraps them in MCP handlers.
"""

import yfinance as yf


def get_stock_price(ticker: str) -> str:
    """Return the current market price for `ticker`."""
    t = yf.Ticker(ticker)
    info = t.info
    name = info.get("shortName") or info.get("longName") or ticker
    price = info.get("regularMarketPrice")
    if price is None:
        raise ValueError(f"No market price available for {ticker}")
    return f"{name} ({ticker}): ${price:.2f}"


def get_history(ticker: str, period: str = "1mo", interval: str = "1d") -> str:
    """Return a text summary of recent price history."""
    t = yf.Ticker(ticker)
    df = t.history(period=period, interval=interval)
    if df.empty:
        raise ValueError(f"No history available for {ticker} ({period})")
    last_close = float(df["Close"].iloc[-1])
    first_close = float(df["Close"].iloc[0])
    change_pct = (last_close - first_close) / first_close * 100
    return (
        f"{ticker} history ({period}, {interval}): "
        f"first ${first_close:.2f}, last ${last_close:.2f}, "
        f"change {change_pct:+.2f}%"
    )


def get_fundamentals(ticker: str) -> str:
    """Return a text summary of key fundamentals."""
    t = yf.Ticker(ticker)
    info = t.info
    name = info.get("shortName") or ticker
    mcap = info.get("marketCap")
    pe = info.get("trailingPE")
    dy = info.get("dividendYield")

    parts = [f"{name} ({ticker}) fundamentals:"]
    if mcap is not None:
        parts.append(f"  market cap: ${mcap / 1e9:.2f}B")
    if pe is not None:
        parts.append(f"  trailing P/E: {pe:.1f}")
    if dy is not None:
        parts.append(f"  dividend yield: {dy * 100:.2f}%")
    return "\n".join(parts)