import requests
import sqlite3
import time
from datetime import datetime

# ══════════════════════════════
# إعدادات
# ══════════════════════════════
BINGX_BASE = "https://open-api.bingx.com"
DB_PATH = "market_data.db"
MAX_PER_REQUEST = 1440

SYMBOLS = [
    "BTC-USDT",
    "SOL-USDT",
    "DOGE-USDT",
    "BNB-USDT",
    "XRP-USDT"
]

TIMEFRAMES = {
    "1m": 10000, # ~7 أيام — للإشارة السريعة
    "5m": 5000, # ~17 يوم — للتأكيد
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

def save_candles(candles, symbol, interval):
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

def load_candles(symbol, interval, limit=None):
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

def count_candles(symbol, interval):
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
def fetch_candles(symbol, interval, target):
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

            print(f" {len(all_candles)}/{target}...")
            time.sleep(0.3)

        except Exception as e:
            print(f"❌ خطأ: {e}")
            break

    return all_candles[:target]

# ══════════════════════════════
# تهيئة كل العملات والفريمات
# ══════════════════════════════
def init_all(symbols=SYMBOLS):
    init_db()
    for symbol in symbols:
        print(f"\n{'─'*40}")
        print(f"🪙 {symbol}")
        for interval, target in TIMEFRAMES.items():
            existing = count_candles(symbol, interval)
            if existing < target:
                candles = fetch_candles(symbol, interval, target)
                save_candles(candles, symbol, interval)
                print(f"✅ {interval}: {count_candles(symbol, interval)} شمعة")
            else:
                print(f"✅ {interval}: {existing} شمعة — جاهز")

# ══════════════════════════════
# تحميل بيانات عملة واحدة
# ══════════════════════════════
def load_symbol_data(symbol):
    import pandas as pd
    result = {}
    for interval in TIMEFRAMES.keys():
        candles = load_candles(symbol, interval)
        if candles:
            result[interval] = pd.DataFrame(candles)
    return result

# ══════════════════════════════
# تحميل بيانات كل العملات
# ══════════════════════════════
def load_all_data(symbols=SYMBOLS):
    return {symbol: load_symbol_data(symbol) for symbol in symbols}

# ══════════════════════════════
# آخر شمعة مباشرة من BingX
# ══════════════════════════════
def get_latest_price(symbol):
    try:
        params = {"symbol": symbol, "interval": "1m", "limit": 1}
        response = requests.get(
            f"{BINGX_BASE}/openApi/swap/v2/quote/klines",
            params=params,
            timeout=10
        ).json()
        candles = response.get("data", [])
        if candles:
            return float(candles[0]["close"])
    except:
        pass
    return None

# ══════════════════════════════
# تشغيل
# ══════════════════════════════
if __name__ == "__main__":
    print("🚀 تهيئة النظام...")
    print("━" * 40)
    init_all()
    print("\n📊 ملخص:")
    for symbol in SYMBOLS:
        for interval in TIMEFRAMES:
            count = count_candles(symbol, interval)
            print(f" {symbol} | {interval}: {count} شمعة")

