import requests
import sqlite3
import time
from datetime import datetime

BINGX_BASE = "https://open-api.bingx.com"
SYMBOL = "BTC-USDT"
DB_PATH = "market_data.db"
MAX_PER_REQUEST = 1440

# ══════════════════════════════
# إعدادات الفريمات
# ══════════════════════════════
TIMEFRAMES = {
    "1m": 50000, # ~35 يوم
    "5m": 20000, # ~70 يوم
    "15m": 10000, # ~104 يوم
}

# ══════════════════════════════
# قاعدة البيانات
# ══════════════════════════════
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS candles (
            timestamp INTEGER,
            symbol TEXT,
            interval TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (timestamp, symbol, interval)
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ قاعدة البيانات جاهزة")

def save_candles(candles, symbol=SYMBOL, interval="5m"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executemany('''
        INSERT OR IGNORE INTO candles
        (timestamp, symbol, interval, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', [(
        candle["timestamp"], symbol, interval,
        candle["open"], candle["high"], candle["low"],
        candle["close"], candle["volume"]
    ) for candle in candles])
    conn.commit()
    conn.close()

def load_candles(symbol=SYMBOL, interval="5m", limit=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if limit:
        c.execute('''
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol=? AND interval=?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (symbol, interval, limit))
    else:
        c.execute('''
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol=? AND interval=?
            ORDER BY timestamp DESC
        ''', (symbol, interval))

    rows = c.fetchall()
    conn.close()
    return [{
        "timestamp": r[0],
        "open": r[1],
        "high": r[2],
        "low": r[3],
        "close": r[4],
        "volume": r[5]
    } for r in reversed(rows)]

def count_candles(symbol=SYMBOL, interval="5m"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM candles WHERE symbol=? AND interval=?',
              (symbol, interval))
    count = c.fetchone()[0]
    conn.close()
    return count

# ══════════════════════════════
# جلب البيانات من BingX
# ══════════════════════════════
def fetch_candles(symbol=SYMBOL, interval="5m", target=20000):
    all_candles = []
    end_time = None

    print(f"📥 جلب {target} شمعة | {symbol} | {interval}")

    while len(all_candles) < target:
        try:
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": MAX_PER_REQUEST
            }
            if end_time:
                params["endTime"] = end_time

            response = requests.get(
                f"{BINGX_BASE}/openApi/swap/v2/quote/klines",
                params=params,
                timeout=10
            ).json()

            candles = response.get("data", [])
            if not candles:
                break

            candles = sorted(candles, key=lambda x: x["time"])
            batch = [{
                "timestamp": int(c["time"]),
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": float(c["volume"])
            } for c in candles]

            all_candles = batch + all_candles
            end_time = candles[0]["time"] - 1

            print(f" 📥 {len(all_candles)}/{target}...")
            time.sleep(0.3)

        except Exception as e:
            print(f"❌ خطأ: {e}")
            break

    return all_candles[:target]

# ══════════════════════════════
# تحميل الـ 3 فريمات دفعة وحدة
# ══════════════════════════════
def init_all_timeframes(symbol=SYMBOL):
    """يجيب ويحفظ الـ 3 فريمات إذا ما موجودة"""
    init_db()

    for interval, target in TIMEFRAMES.items():
        existing = count_candles(symbol, interval)
        print(f"📊 {interval}: موجود {existing}/{target}")

        if existing < target:
            print(f"📥 جلب {interval}...")
            candles = fetch_candles(symbol, interval, target)
            save_candles(candles, symbol, interval)
            print(f"✅ {interval}: تم حفظ {count_candles(symbol, interval)} شمعة")
        else:
            print(f"✅ {interval}: جاهز")

def load_all_timeframes(symbol=SYMBOL):
    """يرجع dict فيه DataFrame لكل فريم"""
    import pandas as pd

    result = {}
    for interval in TIMEFRAMES.keys():
        candles = load_candles(symbol, interval)
        if candles:
            df = pd.DataFrame(candles)
            result[interval] = df
            print(f"✅ {interval}: {len(df)} شمعة محملة")
        else:
            print(f"⚠️ {interval}: ما في بيانات!")

    return result

# ══════════════════════════════
# Helper Functions
# ══════════════════════════════
def get_latest_candle(symbol=SYMBOL, interval="1m"):
    """يجيب آخر شمعة مباشرة من BingX"""
    try:
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": 1
        }
        response = requests.get(
            f"{BINGX_BASE}/openApi/swap/v2/quote/klines",
            params=params,
            timeout=10
        ).json()

        candles = response.get("data", [])
        if not candles:
            return None

        c = candles[0]
        return {
            "timestamp": int(c["time"]),
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"]),
            "volume": float(c["volume"])
        }
    except Exception as e:
        print(f"❌ خطأ جلب آخر شمعة: {e}")
        return None

def get_closes(candles):
    return [c["close"] for c in candles]

def get_volumes(candles):
    return [c["volume"] for c in candles]

def get_highs(candles):
    return [c["high"] for c in candles]

def get_lows(candles):
    return [c["low"] for c in candles]

# ══════════════════════════════
# التشغيل
# ══════════════════════════════
if __name__ == "__main__":
    print("🚀 تهيئة قاعدة البيانات والفريمات...")
    print("━" * 40)

    init_all_timeframes()

    print("\n📊 ملخص البيانات:")
    print("━" * 40)
    for interval in TIMEFRAMES.keys():
        count = count_candles(SYMBOL, interval)
        candles = load_candles(SYMBOL, interval, limit=1)
        if candles:
            last = datetime.fromtimestamp(candles[-1]["timestamp"] / 1000)
            print(f" {interval}: {count} شمعة | آخر شمعة: {last}")

