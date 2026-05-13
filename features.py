import numpy as np
import pandas as pd
from scipy import stats
from scipy.fft import fft

# ══════════════════════════════
# Entropy
# ══════════════════════════════
def entropy(arr):
    hist = np.histogram(arr, bins=10, density=True)[0]
    hist = hist[hist > 0]
    return -np.sum(hist * np.log(hist))


# ══════════════════════════════
# FFT
# ══════════════════════════════
def fourier_strength(arr):
    f = np.abs(fft(arr)[1:len(arr)//2])
    return f.max() / (f.mean() + 1e-10)


# ══════════════════════════════
# Autocorrelation
# ══════════════════════════════
def autocorr(x, lag=1):
    if len(x) <= lag:
        return 0
    x1 = x[:-lag]
    x2 = x[lag:]
    return np.corrcoef(x1, x2)[0, 1]


# ══════════════════════════════
# استخراج Features لفريم واحد
# ══════════════════════════════
def extract_features_single(df, prefix=""):
    df = df.copy()

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    returns = close.pct_change()

    features = {}

    # ────────────────────────
    # 📐 Statistical Layer
    # ────────────────────────
    features[f"{prefix}returns"] = returns

    features[f"{prefix}zscore"] = (
        (close - close.rolling(20).mean()) /
        (close.rolling(20).std() + 1e-10)
    )
    features[f"{prefix}zscore_50"] = (
        (close - close.rolling(50).mean()) /
        (close.rolling(50).std() + 1e-10)
    )

    std20 = returns.rolling(20).std()
    std50 = returns.rolling(50).std()

    features[f"{prefix}std_20"] = std20
    features[f"{prefix}std_50"] = std50

    features[f"{prefix}mean_reversion"] = (
        (close.rolling(20).mean() - close) /
        (close.rolling(20).std() + 1e-10)
    )

    features[f"{prefix}skewness"] = returns.rolling(20).skew()
    features[f"{prefix}kurtosis"] = returns.rolling(20).kurt()

    # ────────────────────────
    # 🌊 Momentum Layer
    # ────────────────────────
    features[f"{prefix}momentum_5"] = close - close.shift(5)
    features[f"{prefix}momentum_10"] = close - close.shift(10)
    features[f"{prefix}momentum_20"] = close - close.shift(20)

    features[f"{prefix}momentum_pct"] = close.pct_change(10)
    features[f"{prefix}acceleration"] = (
        features[f"{prefix}momentum_10"] -
        features[f"{prefix}momentum_10"].shift(5)
    )

    # ────────────────────────
    # 📊 Probability Layer
    # ────────────────────────
    features[f"{prefix}hist_prob_up"] = returns.rolling(50).apply(
        lambda x: (x > 0).mean(), raw=True
    )

    features[f"{prefix}hist_prob_big"] = returns.rolling(50).apply(
        lambda x: (np.abs(x) > np.std(x)).mean(), raw=True
    )

    features[f"{prefix}percentile_rank"] = returns.rolling(50).apply(
        lambda x: stats.percentileofscore(x, x[-1]) / 100, raw=True
    )

    # ────────────────────────
    # 🔢 Advanced Analytics
    # ────────────────────────
    features[f"{prefix}autocorr_1"] = returns.rolling(30).apply(
        lambda x: autocorr(x, 1), raw=True
    )
    features[f"{prefix}autocorr_5"] = returns.rolling(30).apply(
        lambda x: autocorr(x, 5), raw=True
    )

    features[f"{prefix}fourier_strength"] = returns.rolling(50).apply(
        fourier_strength, raw=True
    )

    features[f"{prefix}entropy"] = returns.rolling(20).apply(
        entropy, raw=True
    )

    # ────────────────────────
    # 📈 Market State
    # ────────────────────────
    features[f"{prefix}volatility"] = std20
    features[f"{prefix}vol_ratio"] = std20 / (std50 + 1e-10)

    features[f"{prefix}volume_change"] = volume.pct_change()
    features[f"{prefix}volume_zscore"] = (
        (volume - volume.rolling(20).mean()) /
        (volume.rolling(20).std() + 1e-10)
    )

    features[f"{prefix}price_range"] = (high - low) / (close + 1e-10)
    features[f"{prefix}close_position"] = (close - low) / ((high - low) + 1e-10)

    return pd.DataFrame(features)


# ══════════════════════════════
# استخراج Features لـ 3 فريمات
# ══════════════════════════════
def extract_all_features(dfs: dict) -> pd.DataFrame:
    """
    dfs = {
        "1m": df_1m,
        "5m": df_5m,
        "15m": df_15m,
    }
    يرجع DataFrame موحد مبني على آخر شمعة 1m
    """

    # استخراج features لكل فريم
    feat_1m = extract_features_single(dfs["1m"], prefix="1m_")
    feat_5m = extract_features_single(dfs["5m"], prefix="5m_")
    feat_15m = extract_features_single(dfs["15m"], prefix="15m_")

    # تنظيف كل فريم
    for feat in [feat_1m, feat_5m, feat_15m]:
        feat.replace([np.inf, -np.inf], np.nan, inplace=True)
        feat.dropna(inplace=True)
        feat.reset_index(drop=True, inplace=True)

    # نأخذ آخر صف من 5m و 15m كـ context ثابت
    # ونضيفه على كل صف من 1m
    last_5m = feat_5m.iloc[-1]
    last_15m = feat_15m.iloc[-1]

    # نضيف أعمدة السعر الأساسية من 1m
    for col in ["open", "high", "low", "close", "volume"]:
        if col in dfs["1m"].columns:
            feat_1m[col] = dfs["1m"][col].iloc[-len(feat_1m):].values

    # نضيف الـ context للـ 1m
    for col in last_5m.index:
        feat_1m[col] = last_5m[col]

    for col in last_15m.index:
        feat_1m[col] = last_15m[col]

    feat_1m.replace([np.inf, -np.inf], np.nan, inplace=True)
    feat_1m.dropna(inplace=True)
    feat_1m.reset_index(drop=True, inplace=True)

    return feat_1m


# ══════════════════════════════
# للتوافق مع الكود القديم (فريم وحيد)
# ══════════════════════════════
def extract_features(df):
    """للاستخدام مع فريم وحيد - للتوافق مع backtester و validator"""
    prefix = ""
    feat = extract_features_single(df, prefix="")
    df = df.copy()
    for col in feat.columns:
        df[col] = feat[col].values

    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def load_data(symbol="BTC-USDT", interval="1m"):
    """تحميل بيانات من قاعدة البيانات"""
    import sqlite3
    import os

    DB_PATH = "market_data.db"

    if not os.path.exists(DB_PATH):
        print("📥 DB ما موجودة، جاري جلب البيانات...")
        from data_engine import init_all_timeframes
        init_all_timeframes()

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query('''
        SELECT timestamp, open, high, low, close, volume
        FROM candles
        WHERE symbol=? AND interval=?
        ORDER BY timestamp ASC
    ''', conn, params=(symbol, interval))
    conn.close()
    return df


# ══════════════════════════════
# قائمة كل الـ Features
# ══════════════════════════════
BASE_FEATURES = [
    "returns", "zscore", "zscore_50",
    "std_20", "std_50", "mean_reversion",
    "skewness", "kurtosis",
    "momentum_5", "momentum_10", "momentum_20",
    "momentum_pct", "acceleration",
    "hist_prob_up", "hist_prob_big", "percentile_rank",
    "autocorr_1", "autocorr_5",
    "fourier_strength", "entropy",
    "volatility", "vol_ratio",
    "volume_change", "volume_zscore",
    "price_range", "close_position"
]

ALL_FEATURES = (
    [f"1m_{f}" for f in BASE_FEATURES] +
    [f"5m_{f}" for f in BASE_FEATURES] +
    [f"15m_{f}" for f in BASE_FEATURES]
)


# ══════════════════════════════
# تشغيل
# ══════════════════════════════
if __name__ == "__main__":
    from data_engine import load_all_timeframes, init_all_timeframes

    print("🚀 تحميل الفريمات...")
    init_all_timeframes()
    dfs = load_all_timeframes()

    print("\n⚙️ استخراج الـ Features...")
    df_features = extract_all_features(dfs)

    print(f"\n✅ عدد الصفوف: {len(df_features)}")
    print(f"✅ عدد الـ Features: {len(df_features.columns)}")
    print(f"\n📋 Features (أول 10):")
    print(list(df_features.columns)[:10])
    print(f"\n📊 إحصائيات:")
    print(df_features.describe().round(4))

