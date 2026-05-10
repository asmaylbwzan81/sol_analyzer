
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
    # ── جدول الأنماط الجديد ──
    c.execute("""
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id TEXT,
            symbol TEXT,
            direction TEXT,
            rsi_zone TEXT,
            adx_zone TEXT,
            ema_zone TEXT,
            macd_zone TEXT,
            result TEXT,
            time TEXT
        )
    """)
    conn.commit()
    conn.close()

def _get_zone(value):
    """تحويل القيمة لمنطقة: LOW / MID / HIGH"""
    if value < 0.35:
        return "LOW"
    elif value > 0.65:
        return "HIGH"
    else:
        return "MID"

def save_signal(signal_id, symbol, direction, score, price, scores=None):
    setup_db()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO signals VALUES (NULL,?,?,?,?,?,NULL,NULL,?)
    """, (signal_id, symbol, direction, score, price,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    # ── حفظ النمط لو في scores ──
    if scores:
        c.execute("""
            INSERT INTO patterns VALUES (NULL,?,?,?,?,?,?,?,NULL,?)
        """, (
            signal_id,
            symbol,
            direction,
            _get_zone(scores.get("rsi", 0.5)),
            _get_zone(scores.get("adx", 0.5)),
            _get_zone(scores.get("ema", 0.5)),
            _get_zone(scores.get("macd", 0.5)),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    conn.commit()
    conn.close()

def update_result(signal_id, result, pnl):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE signals SET result=?, pnl=? WHERE signal_id=?",
              (result, pnl, signal_id))
    # ── تحديث النتيجة في جدول الأنماط كمان ──
    c.execute("UPDATE patterns SET result=? WHERE signal_id=?",
              (result, signal_id))
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
    """نسبة فوز العملة — نفس الدالة القديمة"""
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

def get_pattern_stats(scores, direction):
    """
    يرجع إحصائيات النمط المشابه للحالي
    مثل: {'total': 20, 'wins': 14, 'win_rate': 0.70, 'text': '...'}
    """
    setup_db()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    rsi_zone = _get_zone(scores.get("rsi", 0.5))
    adx_zone = _get_zone(scores.get("adx", 0.5))
    ema_zone = _get_zone(scores.get("ema", 0.5))
    macd_zone = _get_zone(scores.get("macd", 0.5))

    c.execute("""
        SELECT result FROM patterns
        WHERE direction=? AND rsi_zone=? AND adx_zone=? AND ema_zone=? AND result IN ('WIN','LOSS')
    """, (direction, rsi_zone, adx_zone, ema_zone))

    data = c.fetchall()
    conn.close()

    if not data:
        return {"total": 0, "wins": 0, "win_rate": 0.5, "text": "لا يوجد سجل تاريخي لهذا النمط"}

    total = len(data)
    wins = sum(1 for d in data if d[0] == "WIN")
    win_rate = round(wins / total, 2)

    text = f"هذا النمط تكرر {total} مرة — فاز {wins} مرة ({int(win_rate*100)}%)"
    return {"total": total, "wins": wins, "win_rate": win_rate, "text": text}

