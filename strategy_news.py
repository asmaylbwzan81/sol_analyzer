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

# أخبار اقتصادية خطيرة
HIGH_IMPACT_KEYWORDS = [
    "fomc", "federal reserve", "fed rate", "interest rate decision",
    "cpi", "inflation", "non-farm", "nfp", "gdp", "unemployment",
    "powell", "rate hike", "rate cut", "quantitative"
]

# وقت التجنب قبل وبعد الخبر (بالدقائق)
AVOID_BEFORE = 15
AVOID_AFTER = 15

# كاش الأخبار (لتجنب الطلبات المتكررة)
_news_cache = {
    "sentiment": None,
    "sentiment_time": 0,
    "calendar": [],
    "calendar_time": 0,
}
CACHE_TTL = 300 # 5 دقائق


# ══════════════════════════════
# Sentiment Analysis
# ══════════════════════════════
def get_sentiment(symbol: str = "bitcoin") -> float:
    now = time.time()

    # كاش
    if _news_cache["sentiment"] and now - _news_cache["sentiment_time"] < CACHE_TTL:
        return _news_cache["sentiment"]

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
        if ratio >= 0.90:
            score = 0.95
        elif ratio >= 0.75:
            score = 0.85
        elif ratio >= 0.60:
            score = 0.75
        elif ratio >= 0.55:
            score = 0.65
        elif ratio >= 0.45:
            score = 0.50
        elif ratio >= 0.40:
            score = 0.40
        elif ratio >= 0.25:
            score = 0.30
        elif ratio >= 0.10:
            score = 0.20
        else:
            score = 0.05

    _news_cache["sentiment"] = score
    _news_cache["sentiment_time"] = now
    return score


# ══════════════════════════════
# Economic Calendar (ForexFactory RSS)
# ══════════════════════════════
def get_economic_events() -> list:
    now = time.time()

    # كاش
    if _news_cache["calendar"] and now - _news_cache["calendar_time"] < CACHE_TTL:
        return _news_cache["calendar"]

    events = []
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        r = requests.get(url, timeout=10)
        data = r.json()

        for event in data:
            impact = event.get("impact", "").lower()
            if impact != "high":
                continue

            title = event.get("title", "").lower()
            date_str = event.get("date", "")
            time_str = event.get("time", "")

            try:
                dt_str = f"{date_str} {time_str}"
                dt = datetime.strptime(dt_str, "%Y-%m-%d %I:%M%p")
                dt = dt.replace(tzinfo=timezone.utc)
                events.append({
                    "title": title,
                    "time": dt,
                    "impact": impact
                })
            except:
                continue

    except Exception as e:
        print(f"⚠️ ما قدرنا نجيب Economic Calendar: {e}")

    _news_cache["calendar"] = events
    _news_cache["calendar_time"] = now
    return events


# ══════════════════════════════
# فحص إذا في خبر خطير قريب
# ══════════════════════════════
def is_high_impact_news_near() -> tuple:
    """
    يرجع (True, اسم الخبر) إذا في خبر خطير خلال AVOID_BEFORE أو AVOID_AFTER دقيقة
    يرجع (False, None) إذا آمن
    """
    now = datetime.now(timezone.utc)
    events = get_economic_events()

    for event in events:
        diff = (event["time"] - now).total_seconds() / 60

        # قبل الخبر بـ AVOID_BEFORE دقيقة
        if 0 < diff <= AVOID_BEFORE:
            return True, f"⏰ خبر قادم خلال {int(diff)} دقيقة: {event['title']}"

        # بعد الخبر بـ AVOID_AFTER دقيقة
        if -AVOID_AFTER <= diff <= 0:
            return True, f"🔴 خبر صدر منذ {int(abs(diff))} دقيقة: {event['title']}"

    return False, None


# ══════════════════════════════
# الفلتر الرئيسي
# ══════════════════════════════
def should_trade(symbol: str = "bitcoin") -> tuple:
    """
    القرار النهائي: هل نفتح صفقة؟
    يرجع (True/False, السبب)
    """

    # 1. تحقق من الأخبار الاقتصادية الخطيرة
    danger, reason = is_high_impact_news_near()
    if danger:
        return False, reason

    # 2. تحقق من Sentiment
    sentiment = get_sentiment(symbol)

    if sentiment <= 0.20:
        return False, f"📰 أخبار سلبية جداً (score={sentiment})"

    if sentiment >= 0.40:
        return True, f"✅ آمن للتداول (sentiment={sentiment})"

    # منطقة رمادية 0.20 - 0.40
    return False, f"⚠️ أخبار سلبية (score={sentiment})"


# ══════════════════════════════
# تشغيل
# ══════════════════════════════
if __name__ == "__main__":
    print("🔍 فحص الأخبار...")

    danger, reason = is_high_impact_news_near()
    if danger:
        print(f"🚫 {reason}")
    else:
        print("✅ لا توجد أخبار اقتصادية خطيرة قريبة")

    sentiment = get_sentiment("bitcoin")
    print(f"📰 Sentiment Score: {sentiment}")

    trade_ok, msg = should_trade("bitcoin")
    print(f"\n{'✅ يمكن التداول' if trade_ok else '🚫 لا تفتح صفقة'}: {msg}")

