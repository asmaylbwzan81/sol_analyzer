import sqlite3
import os
import numpy as np
import pandas as pd
from scipy import stats
from scipy.fft import fft

DB_PATH = "market_data.db"
SYMBOL = "BTC-USDT"
INTERVAL = "5m"


# ══════════════════════════════
# تحميل البيانات
# ══════════════════════════════
def load_data():
    if not os.path.exists(DB_PATH):
        print("📥 DB ما موجودة، جاري جلب البيانات...")
        from data_engine import init_db, fetch_candles, save_candles
        init_db()
        candles = fetch_candles()
        save_candles(candles)

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
# Entropy صحيحة وسريعة
# ══════════════════════════════
def entropy(arr):
    hist = np.histogram(arr, bins=10, density=True)[0]
    hist = hist[hist > 0]
    return -np.sum(hist * np.log(hist))


# ══════════════════════════════
# FFT feature محسّن
# ══════════════════════════════
def fourier_strength(arr):
    f = np.abs(fft(arr)[1:len(arr)//2])
    return f.max() / (f.mean() + 1e-10)


# ══════════════════════════════
# autocorr سريع (بدون pandas)
# ══════════════════════════════
def autocorr(x, lag=1):
    if len(x) <= lag:
        return 0
    x1 = x[:-lag]
    x2 = x[lag:]
    return np.corrcoef(x1, x2)[0, 1]


# ══════════════════════════════
# Features
# ══════════════════════════════
def extract_features(df):

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    returns = close.pct_change()

    # ────────────────────────
    # 📐 Statistical Layer
    # ────────────────────────
    df["returns"] = returns

    df["zscore"] = (close - close.rolling(20).mean()) / (close.rolling(20).std() + 1e-10)
    df["zscore_50"] = (close - close.rolling(50).mean()) / (close.rolling(50).std() + 1e-10)

    std20 = returns.rolling(20).std()
    std50 = returns.rolling(50).std()

    df["std_20"] = std20
    df["std_50"] = std50

    df["mean_reversion"] = (close.rolling(20).mean() - close) / (close.rolling(20).std() + 1e-10)

    df["skewness"] = returns.rolling(20).skew()
    df["kurtosis"] = returns.rolling(20).kurt()

    # ────────────────────────
    # 🌊 Momentum Layer
    # ────────────────────────
    df["momentum_5"] = close - close.shift(5)
    df["momentum_10"] = close - close.shift(10)
    df["momentum_20"] = close - close.shift(20)

    df["momentum_pct"] = close.pct_change(10)
    df["acceleration"] = df["momentum_10"] - df["momentum_10"].shift(5)

    # ────────────────────────
    # 📊 Probability Layer
    # ────────────────────────
    df["hist_prob_up"] = returns.rolling(50).apply(lambda x: (x > 0).mean(), raw=True)

    df["hist_prob_big"] = returns.rolling(50).apply(
        lambda x: (np.abs(x) > np.std(x)).mean(),
        raw=True
    )

    df["percentile_rank"] = returns.rolling(50).apply(
        lambda x: stats.percentileofscore(x, x[-1]) / 100,
        raw=True
    )

    # ────────────────────────
    # 🔢 Advanced Analytics
    # ────────────────────────
    df["autocorr_1"] = returns.rolling(30).apply(lambda x: autocorr(x, 1), raw=True)
    df["autocorr_5"] = returns.rolling(30).apply(lambda x: autocorr(x, 5), raw=True)

    df["fourier_strength"] = returns.rolling(50).apply(fourier_strength, raw=True)

    df["entropy"] = returns.rolling(20).apply(entropy, raw=True)

    # ────────────────────────
    # 📈 Market State
    # ────────────────────────
    df["volatility"] = std20
    df["vol_ratio"] = std20 / (std50 + 1e-10)

    df["volume_change"] = volume.pct_change()
    df["volume_zscore"] = (volume - volume.rolling(20).mean()) / (volume.rolling(20).std() + 1e-10)

    df["price_range"] = (high - low) / (close + 1e-10)
    df["close_position"] = (close - low) / ((high - low) + 1e-10)

    # ────────────────────────
    # تنظيف
    # ────────────────────────
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


# ══════════════════════════════
# تشغيل
# ══════════════════════════════
if __name__ == "__main__":

    print("📊 تحميل البيانات...")
    df = load_data()
    print(f"✅ {len(df)} شمعة")

    print("⚙️ استخراج الـ Features...")
    df = extract_features(df)

    features = [c for c in df.columns if c not in
                ["timestamp", "open", "high", "low", "close", "volume"]]

    print(f"✅ عدد الـ Features: {len(features)}")
    print("\n📋 Features:")
    print(features)

    print("\n📊 إحصائيات:")
    print(df[features].describe().round(4))
