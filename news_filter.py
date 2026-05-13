import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import time

# ══════════════════════════════
# إعدادات
# ══════════════════════════════
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

AVOID_BEFORE = 15
AVOID_AFTER = 15

_cache = {
    "sentiment": None,
    "sentiment_time": 0,
    "calendar": [],
    "calendar_time": 0,
}
CACHE_TTL = 300


# ══════════════════════════════
# Sentiment
# ══════════════════════════════
def get_sentiment(symbol: str = "bitcoin") -> float:
    now = time.time()
    if _cache["sentiment"] and now - _cache["sentiment_time"] < CACHE_TTL:
        return _cache["sentiment"]

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
        score = 0.5
    else:
        ratio = positive / total
        if ratio >= 0.90: score = 0.95
        elif ratio >= 0.75: score = 0.85
        elif ratio >= 0.60: score = 0.75
        elif ratio >= 0.55: score = 0.65
        elif ratio >= 0.45: score = 0.50
        elif ratio >= 0.40: score = 0.40
        elif ratio >= 0.25: score = 0.30
        elif ratio >= 0.10: score = 0.20
        else: score = 0.05

    _cache["sentiment"] = score
    _cache["sentiment_time"] = now
    return score


# ══════════════════════════════
# Economic Calendar
# ══════════════════════════════
def get_economic_events() -> list:
    now = time.time()
    if _cache["calendar"] and now - _cache["calendar_time"] < CACHE_TTL:
        return _cache["calendar"]

    events = []
    urls = [
        "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
        "https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json",
    ]

    for url in urls:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                continue
            data = r.json()
            if not data:
                continue

            for event in data:
                if event.get("impact", "").lower() != "high":
                    continue
                date_str = event.get("date", "")
                time_str = event.get("time", "")
                if not date_str or not time_str or time_str == "All Day":
                    continue
                try:
                    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M%p")
                    dt = dt.replace(tzinfo=timezone.utc)
                    events.append({"title": event.get("title", ""), "time": dt})
                except:
                    continue
            if events:
                break
        except Exception as e:
            continue

    if not events:
        print("⚠️ Economic Calendar غير متاح — نكمل بدونه")

    _cache["calendar"] = events
    _cache["calendar_time"] = now
    return events


# ══════════════════════════════
# فحص الأخبار الخطيرة
# ══════════════════════════════
def is_high_impact_news_near() -> tuple:
    now = datetime.now(timezone.utc)
    events = get_economic_events()

    for event in events:
        diff = (event["time"] - now).total_seconds() / 60
        if 0 < diff <= AVOID_BEFORE:
            return True, f"⏰ خبر قادم خلال {int(diff)} دقيقة: {event['title']}"
        if -AVOID_AFTER <= diff <= 0:
            return True, f"🔴 خبر صدر منذ {int(abs(diff))} دقيقة: {event['title']}"

    return False, None


# ══════════════════════════════
# القرار النهائي
# ══════════════════════════════
def should_trade(symbol: str = "bitcoin") -> tuple:
    danger, reason = is_high_impact_news_near()
    if danger:
        return False, reason

    sentiment = get_sentiment(symbol)

    if sentiment <= 0.20:
        return False, f"📰 أخبار سلبية جداً (score={sentiment})"
    if sentiment >= 0.40:
        return True, f"✅ آمن للتداول (sentiment={sentiment})"

    return False, f"⚠️ أخبار سلبية (score={sentiment})"


# ══════════════════════════════
# تشغيل
# ══════════════════════════════
if __name__ == "__main__":
    print("🔍 فحص الأخبار...")
    danger, reason = is_high_impact_news_near()
    print(f"{'🚫 ' + reason if danger else '✅ لا توجد أخبار خطيرة'}")
    sentiment = get_sentiment("bitcoin")
    print(f"📰 Sentiment: {sentiment}")
    ok, msg = should_trade("bitcoin")
    print(f"\n{'✅' if ok else '🚫'} {msg}")

