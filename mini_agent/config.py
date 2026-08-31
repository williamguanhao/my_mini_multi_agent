import os
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("MINIMAX_API_KEY")
MODEL = os.getenv(
    "MINI_MODEL",
    "MiniMax-M2.5",
)

BASE_URL = os.getenv(
    "MINIMAX_BASE_URL",
    "https://api.minimaxi.com/v1",
)

FRED_API_KEY = os.environ.get("FRED_API_KEY")