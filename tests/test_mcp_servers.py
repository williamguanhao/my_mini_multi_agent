"""Tests for MCP server tool implementations. No MCP here — pure Python."""

import pandas as pd
from unittest.mock import patch


def test_get_stock_price_returns_string():
    from mcp_servers.yfinance.tools import get_stock_price

    fake_info = {"shortName": "Apple Inc.", "regularMarketPrice": 150.25}
    with patch("yfinance.Ticker") as MockTicker:
        MockTicker.return_value.info = fake_info
        result = get_stock_price("AAPL")

    assert isinstance(result, str)
    assert "Apple" in result
    assert "150.25" in result


def test_get_history_returns_string():
    from mcp_servers.yfinance.tools import get_history

    fake_df = pd.DataFrame(
        {"Close": [100.0, 101.5, 102.3]},
        index=pd.date_range("2024-01-01", periods=3),
    )
    with patch("yfinance.Ticker") as MockTicker:
        MockTicker.return_value.history.return_value = fake_df
        result = get_history("AAPL", period="5d")

    assert isinstance(result, str)
    assert "AAPL" in result
    assert "102.3" in result


def test_get_fundamentals_returns_string():
    from mcp_servers.yfinance.tools import get_fundamentals

    fake_info = {
        "shortName": "Apple Inc.",
        "marketCap": 3000000000000,
        "trailingPE": 32.1,
        "dividendYield": 0.005,
    }
    with patch("yfinance.Ticker") as MockTicker:
        MockTicker.return_value.info = fake_info
        result = get_fundamentals("AAPL")

    assert isinstance(result, str)
    assert "Apple" in result
    assert "32.1" in result
    assert "0.50%" in result  # dividend yield formatted as percent (2 decimals)


def test_fred_get_series_returns_string():
    import os
    from mcp_servers.fred import tools as fred_tools

    fake_df = pd.DataFrame(
        {"value": [4.0, 4.25, 4.5]},
        index=pd.date_range("2024-01-01", periods=3),
    )
    with patch.dict(os.environ, {"FRED_API_KEY": "fake-key"}):
        with patch.object(fred_tools, "Fred") as MockFred:
            MockFred.return_value.get_series.return_value = fake_df
            result = fred_tools.get_series("DGS10", start="2024-01-01")

    assert isinstance(result, str)
    assert "DGS10" in result
    assert "4.5" in result


def test_fred_search_series_returns_string():
    import os
    from mcp_servers.fred import tools as fred_tools

    with patch.dict(os.environ, {"FRED_API_KEY": "fake-key"}):
        with patch.object(fred_tools, "Fred") as MockFred:
            MockFred.return_value.search.return_value = pd.DataFrame({
                "id": ["DGS10", "DGS2"],
                "title": ["10-Year Treasury", "2-Year Treasury"],
            })
            result = fred_tools.search_series("treasury")

    assert isinstance(result, str)
    assert "DGS10" in result
    assert "DGS2" in result


def test_fred_get_series_missing_api_key():
    import os
    from mcp_servers.fred.tools import get_series

    with patch.dict(os.environ, {}, clear=True):
        try:
            get_series("DGS10")
            assert False, "expected ValueError"
        except ValueError as e:
            assert "FRED_API_KEY" in str(e)