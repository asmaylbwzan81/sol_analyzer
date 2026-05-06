import sqlite3
import json
import os
from datetime import datetime
from upstash_redis import Redis

DB_FILE = "signals.db"

UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

def setup_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id TEXT,
            symbol TEXT,
            direction TEXT,
            score REAL,
            price REAL,
            result TEXT,
            pnl REAL,
            time TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_signal(signal_id, symbol, direction, score, price):
    setup_db()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO signals VALUES (NULL,?,?,?,?,?,NULL,NULL,?)
    """, (signal_id, symbol, direction, score, price,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def update_result(signal_id, result, pnl):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE signals SET result=?, pnl=? WHERE signal_id=?",
              (result, pnl, signal_id))
    conn.commit()
    conn.close()

def check_results_from_redis():
    """يقرأ النتائج من Redis ويحدث الذاكرة"""
    try:
        r = Redis(url=UPSTASH_URL, token=UPSTASH_TOKEN)
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT signal_id FROM signals WHERE result IS NULL")
        pending = c.fetchall()
        conn.close()

        for (signal_id,) in pending:
            try:
                data = r.get(f"result:{signal_id}")
                if data:
                    result_data = json.loads(str(data))
                    result = result_data.get("result")
                    pnl = result_data.get("pnl_pct", 0)
                    if result in ["WIN", "LOSS", "REJECTED"]:
                        update_result(signal_id, result, pnl)
                        print(f"✅ تحديث الذاكرة: {signal_id} = {result}")
            except:
                continue
    except Exception as e:
        print(f"⚠️ خطأ قراءة النتائج: {e}")

def analyze(symbol):
    setup_db()
    check_results_from_redis()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT result FROM signals WHERE symbol=? AND result IN ('WIN', 'LOSS')", (symbol,))
    data = c.fetchall()
    conn.close()

    if not data:
        return 0.5

    wins = sum(1 for d in data if d[0] == "WIN")
    return wins / len(data)
