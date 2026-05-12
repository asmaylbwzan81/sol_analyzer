import requests
import sqlite3
import time
from datetime import datetime

BINGX_BASE = "https://open-api.bingx.com"
SYMBOL = "BTC-USDT"
INTERVAL = "5m"
TARGET_CANDLES = 20000
MAX_PER_REQUEST = 1440
DB_PATH = "market_data.db"

# ══════════════════════════════
# قاعدة البيانات
# ══════════════════════════════
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS candles (
            timestamp INTEGER PRIMARY KEY,
            symbol TEXT,
            interval TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL
        )
    ''')
    conn.commit()
    conn.close()

def save_candles(candles, symbol=SYMBOL, interval=INTERVAL):
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

def load_candles(symbol=SYMBOL, interval=INTERVAL, limit=TARGET_CANDLES):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT timestamp, open, high, low, close, volume
        FROM candles
        WHERE symbol=? AND interval=?
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (symbol, interval, limit))
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

def count_candles(symbol=SYMBOL, interval=INTERVAL):
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
def fetch_candles(symbol=SYMBOL, interval=INTERVAL, target=TARGET_CANDLES):
    all_candles = []
    end_time = None

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

            print(f"📥 جمعنا {len(all_candles)} شمعة...")
            time.sleep(0.3)

        except Exception as e:
            print(f"❌ خطأ: {e}")
            break

    return all_candles[:target]

# ══════════════════════════════
# Helper Functions
# ══════════════════════════════
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
    init_db()

    existing = count_candles()
    print(f"📊 الموجود في قاعدة البيانات: {existing} شمعة")

    if existing < TARGET_CANDLES:
        print("📥 جاري جلب البيانات من BingX...")
        candles = fetch_candles()
        save_candles(candles)
        print(f"✅ تم الحفظ: {count_candles()} شمعة")
    else:
        print("✅ البيانات موجودة، نحمّل من قاعدة البيانات")

    candles = load_candles()
    print(f"📅 من: {datetime.fromtimestamp(candles[0]['timestamp']/1000)}")
    print(f"📅 إلى: {datetime.fromtimestamp(candles[-1]['timestamp']/1000)}")
    print(f"🕯️ عدد الشموع: {len(candles)}")
