import requests
import os

CRYPTOPANIC_KEY = os.getenv("CRYPTOPANIC_KEY", "")

def analyze(symbol="ETH-USDT"):
    coin = symbol.replace("-USDT", "").replace("-BUSD", "")

    try:
        url = f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_KEY}&currencies={coin}&filter=hot"
        data = requests.get(url, timeout=5).json()
        posts = data.get("results", [])

        if not posts:
            return 0.5

        bullish = sum(1 for p in posts if p.get("votes", {}).get("positive", 0) > p.get("votes", {}).get("negative", 0))
        bearish = sum(1 for p in posts if p.get("votes", {}).get("negative", 0) > p.get("votes", {}).get("positive", 0))
        total = bullish + bearish

        if total == 0:
            return 0.5

        score = bullish / total

        if score > 0.7:
            return 0.80
        elif score > 0.5:
            return 0.60
        elif score < 0.3:
            return 0.20
        elif score < 0.5:
            return 0.40
        return 0.5

    except:
        return 0.5
