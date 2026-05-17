import asyncio
import aiohttp
import sqlite3
import pandas as pd
import numpy as np
import time

# ══════════════════════════════
# إعدادات هندسية ثابتة
# ══════════════════════════════
BINGX_BASE = "https://open-api.bingx.com"
DB_PATH = "market_data.db"
MAX_PER_REQUEST = 1440

SYMBOLS = ["BTC-USDT", "SOL-USDT", "DOGE-USDT", "BNB-USDT", "XRP-USDT"]

TIMEFRAMES = {
    "1m": 10000, # شمعة الدقيقة
    "5m": 5000, # شمعة الـ 5 دقائق
}

# ══════════════════════════════
# إدارة قاعدة البيانات (SQLite)
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
    print("✅ قاعدة البيانات المتزامنة جاهزة")

def save_candles(candles, symbol, interval):
    if not candles:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executemany('''
        INSERT OR IGNORE INTO candles
        (timestamp, symbol, interval, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', [(
        c["timestamp"], symbol, interval,
        c["open"], c["high"], c["low"], c["close"], c["volume"]
    ) for c in candles])
    conn.commit()
    conn.close()

def count_candles(symbol, interval):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM candles WHERE symbol=? AND interval=?', (symbol, interval))
    count = c.fetchone()[0]
    conn.close()
    return count

def load_candles_to_df(symbol, interval):
    """تحميل البيانات مباشرة في قالب Pandas DataFrame متوافق مع محرك الخصائص"""
    conn = sqlite3.connect(DB_PATH)
    query = '''
        SELECT timestamp, open, high, low, close, volume
        FROM candles
        WHERE symbol=? AND interval=?
        ORDER BY timestamp ASC
    '''
    df = pd.read_sql_query(query, conn, params=(symbol, interval))
    conn.close()
    return df

# ══════════════════════════════
# جلب البيانات بشكل متوازٍ (Async Fetching)
# ══════════════════════════════
async def fetch_candles_async(session, symbol, interval, target):
    all_candles = []
    end_time = None
    existing = count_candles(symbol, interval)
    
    if existing >= target:
        print(f"✅ {symbol} | {interval} جاهز مسبقاً ({existing} شمعة)")
        return

    print(f"📥 بدء جلب {target} شمعة لـ {symbol} فريم {interval}...")

    while len(all_candles) < (target - existing):
        try:
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": str(MAX_PER_REQUEST)
            }
            if end_time:
                params["endTime"] = str(end_time)

            url = f"{BINGX_BASE}/openApi/swap/v2/quote/klines"
            async with session.get(url, params=params, timeout=15) as response:
                res_json = await response.json()
                candles = res_json.get("data", [])
                
                if not candles:
                    break

                # ترتيب وتوحيد الحقول لتتوافق مع محرك الاستخراج
                candles = sorted(candles, key=lambda x: int(x["time"]))
                batch = [{
                    "timestamp": int(c["time"]),
                    "open": float(c["open"]),
                    "high": float(c["high"]),
                    "low": float(c["low"]),
                    "close": float(c["close"]),
                    "volume": float(c["volume"])
                } for c in candles]

                all_candles = batch + all_candles
                end_time = int(candles[0]["time"]) - 1
                
                # تعليق ميكروي لتجنب الحظر
                await asyncio.sleep(0.1)

        except Exception as e:
            print(f"❌ خطأ أثناء جلب {symbol} | {interval}: {e}")
            break

    save_candles(all_candles, symbol, interval)
    print(f"💾 تم حفظ بيانات {symbol} | {interval} بنجاح.")

async def pipeline_init_all():
    init_db()
    async with aiohttp.ClientSession() as session:
        tasks = []
        for symbol in SYMBOLS:
            for interval, target in TIMEFRAMES.items():
                tasks.append(fetch_candles_async(session, symbol, interval, target))
        # تشغيل جميع المهام في نفس الأجزاء من الثانية بالتوازي
        await asyncio.gather(*tasks)

# ══════════════════════════════
# تحميل حزم البيانات الموحدة للمحرك الرياضي
# ══════════════════════════════
def load_all_data_for_engine():
    """تجهيز البيانات بالصيغة المصفوفيّة المباشرة المدعومة من كود الخصائص"""
    all_data = {}
    for symbol in SYMBOLS:
        df_1m = load_candles_to_df(symbol, "1m")
        df_5m = load_candles_to_df(symbol, "5m")
        all_data[symbol] = {"1m": df_1m, "5m": df_5m}
    return all_data

# ══════════════════════════════
# نقطة التشغيل الأساسية
# ══════════════════════════════
if __name__ == "__main__":
    print("🚀 إطلاق محرك جلب البيانات غير المتزامن الحجمي...")
    print("━" * 50)
    
    # تشغيل حلقة الـ Async
    asyncio.run(pipeline_init_all())
    
    print("\n📊 ملخص حجم البيانات النهائي في قاعدة البيانات:")
    for symbol in SYMBOLS:
        for interval in TIMEFRAMES:
            print(f" {symbol} | {interval}: {count_candles(symbol, interval)} شمعة")

