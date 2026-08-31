from ..tool import Tool
import yfinance

class GetYfOHLCVTool(Tool):

    @property
    def name(self):
        return "get_yfiance_stock_OHLCV_data"

    @property
    def description(self):
        return "Get ticker OHLCV data for a given period of time from yfinance."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                    "ticker": {
                    "type": "string",
                    "description": (
                        "Ticker to query a stock like"
                        "AAPL, MSFT"
                    ),
            },

                    "start": {
                    "type": "string",
                    "description": (
                        "start date like"
                        "2019-01-01"
                    ),
            },

                    "end": {
                    "type": "string",
                    "description": (
                        "end date like"
                        "2025-01-01"
                    ),
            },

            },
            "required": ["ticker","start","end"],
        }

    def execute(self, argument):
        raw = yfinance.download(
            argument["ticker"],
            start=argument["start"],
            end=argument["end"],
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        return raw.to_json()


class GetYfOptionTool(Tool):

    @property
    def name(self):
        return "get_yfiance_option_data"

    @property
    def description(self):
        return "Get ticker option data from yfinance."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                    "ticker": {
                    "type": "string",
                    "description": (
                        "Ticker to query a stock like"
                        "AAPL, MSFT"
                    ),
            },

                    "start": {
                    "type": "string",
                    "description": (
                        "start date like"
                        "2019-01-01"
                    ),
            },

                    "end": {
                    "type": "string",
                    "description": (
                        "end date like"
                        "2025-01-01"
                    ),
            },

            },
            "required": ["ticker","start","end"],
        }

    def execute(self, argument):

        return 