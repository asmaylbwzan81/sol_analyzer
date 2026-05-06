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

    if score >= 0.90:
        return 0.95 # أخبار إيجابية جداً جداً
    elif score >= 0.75:
        return 0.85 # أخبار إيجابية قوية
    elif score >= 0.60:
        return 0.75 # أخبار إيجابية واضحة
    elif score >= 0.55:
        return 0.65 # أخبار إيجابية خفيفة
    elif score >= 0.45:
        return 0.50 # أخبار محايدة
    elif score >= 0.40:
        return 0.40 # أخبار سلبية خفيفة
    elif score >= 0.25:
        return 0.30 # أخبار سلبية واضحة
    elif score >= 0.10:
        return 0.20 # أخبار سلبية قوية
    else:
        return 0.05 # أخبار سلبية جداً جداً

