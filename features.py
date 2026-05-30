import numpy as np
import pandas as pd
from scipy.fft import fft

WINDOW_SHORT = 20
WINDOW_LONG = 50

def calc_zscore(series, window=WINDOW_SHORT):
    rolling_mean = series.rolling(window).mean()
    rolling_std = series.rolling(window).std()
    return (series - rolling_mean) / (rolling_std + 1e-10)

def calc_mean_reversion(series, window=WINDOW_SHORT):
    rolling_mean = series.rolling(window).mean()
    return (series - rolling_mean) / (rolling_mean + 1e-10)

def calc_momentum(series, periods=5):
    return series.pct_change(periods)

def calc_volatility(series, window=WINDOW_SHORT):
    return series.pct_change().rolling(window).std()

def calc_volume_ratio(volume, window=WINDOW_SHORT):
    return volume / (volume.rolling(window).mean() + 1e-10)

def calc_close_position(high, low, close):
    return (close - low) / (high - low + 1e-10)

def calc_price_range(high, low, close):
    return (high - low) / (close + 1e-10)

def _rolling_autocorr(x):
    if len(x) < 2 or np.std(x) == 0:
        return 0.0
    s = pd.Series(x)
    return float(s.autocorr(lag=1))

def calc_autocorrelation(series, window=WINDOW_SHORT):
    return series.rolling(window).apply(_rolling_autocorr, raw=True).fillna(0)

def _rolling_entropy(x):
    returns = np.diff(x) / (x[:-1] + 1e-10)
    hist, _ = np.histogram(returns, bins=10)
    hist = hist + 1e-10
    probs = hist / hist.sum()
    entropy = float(-np.sum(probs * np.log(probs)))
    max_entropy = np.log(10)
    return entropy / max_entropy

def calc_entropy(series, window=WINDOW_SHORT):
    return series.rolling(window).apply(_rolling_entropy, raw=True).fillna(0)

def _rolling_fourier(x):
    N = len(x)
    chunk_detrended = x - np.mean(x)
    fft_vals = np.abs(fft(chunk_detrended))
    half_vals = fft_vals[1:N//2]
    if len(half_vals) == 0:
        return 0.0
    mean_val = np.mean(half_vals)
    raw = float(np.max(half_vals) / (mean_val + 1e-10))
    return min(raw / 50.0, 1.0)

def calc_fourier_strength(series, window=WINDOW_SHORT):
    return series.rolling(window).apply(_rolling_fourier, raw=True).fillna(0)

def detect_regime(df, window=50):
    close = df["close"]
    returns = close.pct_change()

    # 1️⃣ Trend Strength — linear regression slope
    def trend_slope(x):
        if len(x) < 5: return 0.0
        y = np.array(x)
        t = np.arange(len(y))
        slope, _ = np.polyfit(t, y, 1)
        return slope / (y.mean() + 1e-10)

    trend_strength = close.rolling(window).apply(trend_slope, raw=True).fillna(0)

    # 2️⃣ Volatility — ATR-based ratio
    vol = returns.rolling(window).std()
    vol_mean= vol.rolling(window * 2).mean()
    vol_ratio = vol / (vol_mean + 1e-10)

    # 3️⃣ Noise — entropy-based
    def noise_level(x):
        r = np.diff(x) / (x[:-1] + 1e-10)
        h, _ = np.histogram(r, bins=8)
        h = h + 1e-10
        p = h / h.sum()
        return float(-np.sum(p * np.log(p))) / np.log(8)

    noise = close.rolling(window).apply(noise_level, raw=True).fillna(0.5)

    # ─── القرار النهائي ───
    regime = pd.Series("ranging", index=df.index)

    # trending: ترند قوي + noise منخفض
    trending_mask = (trend_strength.abs() > 0.0008) & (noise < 0.75)
    regime[trending_mask] = "trending"

    # volatile: تذبذب عالي
    volatile_mask = vol_ratio > 1.8
    regime[volatile_mask] = "volatile"

    return regime

def extract_features(df, prefix=""):
    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    p = f"{prefix}_" if prefix else ""

    df[f"{p}zscore_20"] = calc_zscore(close, 20)
    df[f"{p}zscore_50"] = calc_zscore(close, 50)
    df[f"{p}mean_rev_20"] = calc_mean_reversion(close, 20)
    df[f"{p}mean_rev_50"] = calc_mean_reversion(close, 50)
    df[f"{p}momentum_5"] = calc_momentum(close, 5)
    df[f"{p}momentum_10"] = calc_momentum(close, 10)
    df[f"{p}momentum_20"] = calc_momentum(close, 20)
    df[f"{p}volatility_20"] = calc_volatility(close, 20)
    df[f"{p}vol_ratio"] = calc_volume_ratio(volume, 20)
    df[f"{p}close_position"] = calc_close_position(high, low, close)
    df[f"{p}price_range"] = calc_price_range(high, low, close)
    df[f"{p}autocorr"] = calc_autocorrelation(close, window=20)
    df[f"{p}entropy"] = calc_entropy(close, window=20)
    df[f"{p}fourier"] = calc_fourier_strength(close, window=20)
    df[f"{p}returns"] = close.pct_change()
    df[f"{p}returns_5"] = close.pct_change(5)
    df[f"{p}regime"] = detect_regime(df)

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(0)
    return df

# ══════════════════════════════
# دمج 1m + 5m + 15m
# ══════════════════════════════
def extract_all_features(symbol_data):
    df_1m = symbol_data.get("1m")
    df_5m = symbol_data.get("5m")
    df_15m = symbol_data.get("15m") # ✅ جديد

    if df_1m is None or df_1m.empty:
        return None

    if "timestamp" not in df_1m.columns and not isinstance(df_1m.index, pd.DatetimeIndex):
        df_1m = df_1m.reset_index()
    if df_5m is not None and "timestamp" not in df_5m.columns:
        df_5m = df_5m.reset_index()
    if df_15m is not None and "timestamp" not in df_15m.columns:
        df_15m = df_15m.reset_index()

    df_1m_feats = extract_features(df_1m, prefix="1m")

    # ✅ دمج 5m
    if df_5m is not None and not df_5m.empty:
        df_5m_feats = extract_features(df_5m, prefix="5m")
        five_m_cols = [col for col in df_5m_feats.columns if col.startswith("5m_")] + ["timestamp"]
        df_1m_feats = pd.merge_asof(
            df_1m_feats.sort_values("timestamp"),
            df_5m_feats[five_m_cols].sort_values("timestamp"),
            on="timestamp", direction="backward"
        )

    # ✅ دمج 15m — جديد بدون تغيير أي شي موجود
    if df_15m is not None and not df_15m.empty:
        df_15m_feats = extract_features(df_15m, prefix="15m")
        fifteen_m_cols = [col for col in df_15m_feats.columns if col.startswith("15m_")] + ["timestamp"]
        df_1m_feats = pd.merge_asof(
            df_1m_feats.sort_values("timestamp"),
            df_15m_feats[fifteen_m_cols].sort_values("timestamp"),
            on="timestamp", direction="backward"
        )

    numeric_cols = df_1m_feats.select_dtypes(include=[np.number]).columns
    df_1m_feats[numeric_cols] = df_1m_feats[numeric_cols].fillna(0)

    return df_1m_feats


def compute_regime_confidence(df_1m, df_5m, df_15m):
    """
    يرجع: (regime_bias, confidence 0-100)
    """
    def safe_last_regime(df):
        if df is None or df.empty:
            return "unknown"
        r = detect_regime(df)
        return str(r.iloc[-1]) if r is not None and len(r) else "unknown"

    r1 = safe_last_regime(df_1m)
    r5 = safe_last_regime(df_5m)
    r15 = safe_last_regime(df_15m)

    regimes = [r for r in [r1, r5, r15] if r != "unknown"]
    if not regimes:
        return "ranging", 0.0

    counts = {u: regimes.count(u) for u in set(regimes)}
    dominant = max(counts, key=counts.get)

    score = 0.0
    weight_sum = 0.0
    if r1 != "unknown": score += (r1 == dominant) * 1.0; weight_sum += 1.0
    if r5 != "unknown": score += (r5 == dominant) * 1.5; weight_sum += 1.5
    if r15 != "unknown": score += (r15 == dominant) * 2.0; weight_sum += 2.0

    confidence = (score / (weight_sum + 1e-9)) * 100
    return dominant, round(confidence, 2)


FEATURE_NAMES_1M = [f"1m_{x}" for x in ["zscore_20", "zscore_50", "mean_rev_20", "mean_rev_50", "momentum_5", "momentum_10", "momentum_20", "volatility_20", "vol_ratio", "close_position", "price_range", "autocorr", "entropy", "fourier", "returns", "returns_5"]]
FEATURE_NAMES_5M = [f"5m_{x}" for x in ["zscore_20", "zscore_50", "mean_rev_20", "mean_rev_50", "momentum_5", "momentum_10", "momentum_20", "volatility_20", "vol_ratio", "close_position", "price_range", "autocorr", "entropy", "fourier", "returns", "returns_5"]]
FEATURE_NAMES_15M = [f"15m_{x}" for x in ["zscore_20", "zscore_50", "mean_rev_20", "mean_rev_50", "momentum_5", "momentum_10", "momentum_20", "volatility_20", "vol_ratio", "close_position", "price_range", "autocorr", "entropy", "fourier", "returns", "returns_5"]]
ALL_FEATURES = FEATURE_NAMES_1M + FEATURE_NAMES_5M + FEATURE_NAMES_15M

if __name__ == "__main__":
    print(f"🚀 المحرك جاهز: {len(ALL_FEATURES)} خصائص")
    print("✅ 1m + 5m + 15m features")

