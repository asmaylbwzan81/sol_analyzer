import sqlite3
from datetime import datetime

DB_FILE = "signals.db"

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

def analyze(symbol):
    setup_db()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT result FROM signals WHERE symbol=? AND result IS NOT NULL", (symbol,))
    data = c.fetchall()
    conn.close()

    if not data:
        return 0.5

    wins = sum(1 for d in data if d[0] == "WIN")
    return wins / len(data)
