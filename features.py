import numpy as np
import pandas as pd
from scipy.fft import fft

# ══════════════════════════════
# إعدادات هندسية ثابتة
# ══════════════════════════════
WINDOW_SHORT = 20
WINDOW_LONG = 50

# ══════════════════════════════
# المؤشرات الكمية المحسنة (Vectorized)
# ══════════════════════════════

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

# ══════════════════════════════
# تحسينات الدوال المتقدمة عبر Vectorization
# ══════════════════════════════

def _rolling_autocorr(x):
    """حساب التكور الذاتي السريع للمصفوفة"""
    if len(x) < 2 or np.std(x) == 0:
        return 0.0
    s = pd.Series(x)
    return float(s.autocorr(lag=1))

def calc_autocorrelation(series, window=WINDOW_SHORT):
    return series.rolling(window).apply(_rolling_autocorr, raw=True).fillna(0)

def _rolling_entropy(x):
    """
    ✅ حساب الأنتروبي الموحّد بين 0 و1
    الإصلاح: استخدام histogram عادي + normalize يدوي بدل density=True
    density=True كان يرجع probability density وليس probability → قيم ضخمة وسالبة
    """
    returns = np.diff(x) / (x[:-1] + 1e-10)
    hist, _ = np.histogram(returns, bins=10)
    hist = hist + 1e-10
    probs = hist / hist.sum() # ← normalize صحيح
    entropy = float(-np.sum(probs * np.log(probs)))
    max_entropy = np.log(10) # ← أقصى قيمة ممكنة (log bins)
    return entropy / max_entropy # ← النتيجة دائماً بين 0 و1

def calc_entropy(series, window=WINDOW_SHORT):
    return series.rolling(window).apply(_rolling_entropy, raw=True).fillna(0)

def _rolling_fourier(x):
    """
    ✅ حساب طيف فورير الموحّد بين 0 و1
    الإصلاح: تقييد النتيجة بسقف واقعي (50) بدل إرجاع نسبة max/mean مباشرة
    النسبة الخام كانت تطلع 18000-55000 → تمنع أي إشارة
    """
    N = len(x)
    chunk_detrended = x - np.mean(x)
    fft_vals = np.abs(fft(chunk_detrended))
    half_vals = fft_vals[1:N//2]
    if len(half_vals) == 0:
        return 0.0
    mean_val = np.mean(half_vals)
    raw = float(np.max(half_vals) / (mean_val + 1e-10))
    return min(raw / 50.0, 1.0) # ← normalize، 50 سقف واقعي

def calc_fourier_strength(series, window=WINDOW_SHORT):
    return series.rolling(window).apply(_rolling_fourier, raw=True).fillna(0)

# ══════════════════════════════
# كشف حالة السوق (Regime Detection)
# ══════════════════════════════
def detect_regime(df, window=WINDOW_LONG):
    returns = df["close"].pct_change()
    vol = returns.rolling(window).std()
    vol_mean = vol.rolling(window * 2).mean()
    trend = (df["close"].rolling(window).mean().pct_change(10)).abs()

    regime = pd.Series("ranging", index=df.index)
    regime[trend > 0.005] = "trending"
    regime[vol > vol_mean * 2] = "volatile"
    return regime

# ══════════════════════════════
# استخراج الميزات الأساسي
# ══════════════════════════════
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

    # fillna للأرقام فقط، مع الحفاظ على regime كـ string
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(0)
    return df

# ══════════════════════════════
# دمج ومحاذاة التوقيت الصحيح (1m + 5m)
# ══════════════════════════════
def extract_all_features(symbol_data):
    df_1m = symbol_data.get("1m")
    df_5m = symbol_data.get("5m")

    if df_1m is None or df_1m.empty:
        return None

    if "timestamp" not in df_1m.columns and not isinstance(df_1m.index, pd.DatetimeIndex):
        df_1m = df_1m.reset_index()
    if df_5m is not None and "timestamp" not in df_5m.columns and not isinstance(df_5m.index, pd.DatetimeIndex):
        df_5m = df_5m.reset_index()

    df_1m_feats = extract_features(df_1m, prefix="1m")

    if df_5m is not None and not df_5m.empty:
        df_5m_feats = extract_features(df_5m, prefix="5m")

        five_m_cols = [col for col in df_5m_feats.columns if col.startswith("5m_")] + ["timestamp"]
        df_5m_filtered = df_5m_feats[five_m_cols]

        df_1m_feats = pd.merge_asof(
            df_1m_feats.sort_values("timestamp"),
            df_5m_filtered.sort_values("timestamp"),
            on="timestamp",
            direction="backward"
        )

    # fillna للأرقام فقط بعد الدمج، مع الحفاظ على regime كـ string
    numeric_cols = df_1m_feats.select_dtypes(include=[np.number]).columns
    df_1m_feats[numeric_cols] = df_1m_feats[numeric_cols].fillna(0)

    return df_1m_feats


FEATURE_NAMES_1M = [f"1m_{x}" for x in ["zscore_20", "zscore_50", "mean_rev_20", "mean_rev_50", "momentum_5", "momentum_10", "momentum_20", "volatility_20", "vol_ratio", "close_position", "price_range", "autocorr", "entropy", "fourier", "returns", "returns_5"]]
FEATURE_NAMES_5M = [f"5m_{x}" for x in ["zscore_20", "zscore_50", "mean_rev_20", "mean_rev_50", "momentum_5", "momentum_10", "momentum_20", "volatility_20", "vol_ratio", "close_position", "price_range", "autocorr", "entropy", "fourier", "returns", "returns_5"]]
ALL_FEATURES = FEATURE_NAMES_1M + FEATURE_NAMES_5M

if __name__ == "__main__":
    print(f"🚀 المحرك فائق السرعة جاهز: تم استخراج {len(ALL_FEATURES)} خصائص احتمالية.")
    print("✅ entropy موحّد: 0.0 → 1.0")
    print("✅ fourier موحّد: 0.0 → 1.0")

