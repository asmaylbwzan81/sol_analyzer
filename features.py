import sqlite3
import numpy as np
import pandas as pd

DB_PATH = "market_data.db"
SYMBOL = "BTC-USDT"
INTERVAL = "5m"

# ══════════════════════════════
# تحميل البيانات
# ══════════════════════════════
def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query('''
        SELECT timestamp, open, high, low, close, volume
        FROM candles
        WHERE symbol=? AND interval=?
        ORDER BY timestamp ASC
    ''', conn, params=(SYMBOL, INTERVAL))
    conn.close()
    return df

# ══════════════════════════════
# حساب الـ Features
# ══════════════════════════════
def extract_features(df):
    # 1️⃣ Returns
    df["returns"] = df["close"].pct_change()

    # 2️⃣ Z-Score
    df["zscore"] = (
        (df["close"] - df["close"].rolling(20).mean())
        / df["close"].rolling(20).std()
    )

    # 3️⃣ Volatility
    df["volatility"] = df["returns"].rolling(20).std()

    # 4️⃣ Momentum
    df["momentum"] = df["close"] - df["close"].shift(10)

    # 5️⃣ Volume Change
    df["volume_change"] = df["volume"].pct_change()

    # تنظيف NaN
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df

# ══════════════════════════════
# التشغيل
# ══════════════════════════════
if __name__ == "__main__":
    print("📊 تحميل البيانات...")
    df = load_data()
    print(f"✅ {len(df)} شمعة")

    print("📐 حساب الـ Features...")
    df = extract_features(df)
    print(f"✅ جاهز: {len(df)} صف")
    print(f"\n📋 أول 3 صفوف:\n{df[['close','returns','zscore','volatility','momentum','volume_change']].head(3)}")
    print(f"\n📊 إحصاء:\n{df[['zscore','volatility','momentum']].describe().round(4)}")
