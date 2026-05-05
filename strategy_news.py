import requests
import xml.etree.ElementTree as ET

NEWS_SOURCES = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
]

KEYWORDS_POSITIVE = [
    "bull", "surge", "rally", "gain", "rise", "adoption",
    "partnership", "upgrade", "bullish", "pump", "ath"
]

KEYWORDS_NEGATIVE = [
    "bear", "crash", "drop", "fall", "hack", "ban",
    "lawsuit", "bearish", "dump", "sell", "risk"
]

def analyze(symbol: str) -> float:
    positive = 0
    negative = 0

    for url in NEWS_SOURCES:
        try:
            r = requests.get(url, timeout=10)
            root = ET.fromstring(r.content)
            for item in root.iter("item"):
                title = item.find("title")
                if title is None:
                    continue
                title = title.text.lower()
                if symbol.lower() not in title:
                    continue
                for word in KEYWORDS_POSITIVE:
                    if word in title:
                        positive += 1
                        break
                for word in KEYWORDS_NEGATIVE:
                    if word in title:
                        negative += 1
                        break
        except:
            continue

    total = positive + negative
    if total == 0:
        return 0.5

    score = positive / total

    if score > 0.7:
        return 0.80
    elif score > 0.5:
        return 0.60
    elif score < 0.3:
        return 0.20
    elif score < 0.5:
        return 0.40
    return 0.5
