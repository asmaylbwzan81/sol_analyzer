import requests
import random

BINGX_BASE = "https://open-api.bingx.com"

def get_klines(symbol="ETH-USDT", interval="1h", limit=100):
    try:
        url = f"{BINGX_BASE}/openApi/swap/v2/quote/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        data = requests.get(url, params=params, timeout=5).json()
        candles = data.get("data", [])
        return [float(c["close"]) for c in candles]
    except:
        return [100 + random.uniform(-1, 1) for _ in range(limit)]

def get_candles(symbol="ETH-USDT", interval="1h", limit=100):
    try:
        url = f"{BINGX_BASE}/openApi/swap/v2/quote/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        data = requests.get(url, params=params, timeout=5).json()
        candles = data.get("data", [])
        return [{
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"]),
            "volume": float(c["volume"])
        } for c in candles]
    except:
        return []
