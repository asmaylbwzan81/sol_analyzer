import numpy as np
import pandas as pd
from scipy.stats import zscore
from scipy.fft import fft

# ══════════════════════════════
# إعدادات
# ══════════════════════════════
WINDOW_SHORT = 20 # للحسابات السريعة (1m)
WINDOW_LONG = 50 # للحسابات الأبطأ (5m)

# ══════════════════════════════
# المؤشرات الكمية الأساسية
# ══════════════════════════════

def calc_zscore(series, window=WINDOW_SHORT):
    """انحراف السعر عن المتوسط"""
    mean = series.rolling(window).mean()
    std = series.rolling(window).std()
    return (series - mean) / (std + 1e-10)

def calc_mean_reversion(series, window=WINDOW_SHORT):
    """قوة الارتداد للمتوسط"""
    mean = series.rolling(window).mean()
    return (series - mean) / (mean + 1e-10)

def calc_momentum(series, periods=5):
    """قوة الحركة"""
    return series.pct_change(periods)

def calc_volatility(series, window=WINDOW_SHORT):
    """التذبذب اللحظي"""
    returns = series.pct_change()
    return returns.rolling(window).std()

def calc_autocorrelation(series, lag=1, window=WINDOW_SHORT):
    """تكرار الأنماط"""
    result = []
    for i in range(len(series)):
        if i < window + lag:
            result.append(0.0)
            continue
        chunk = series.iloc[i-window:i]
        if len(chunk) < window:
            result.append(0.0)
            continue
        try:
            corr = chunk.autocorr(lag=lag)
            result.append(corr if not np.isnan(corr) else 0.0)
        except:
            result.append(0.0)
    return pd.Series(result, index=series.index)

def calc_entropy(series, window=WINDOW_SHORT):
    """فوضى السوق — عالية = فوضى، منخفضة = نمط"""
    result = []
    for i in range(len(series)):
        if i < window:
            result.append(1.0)
            continue
        chunk = series.iloc[i-window:i].values
        returns = np.diff(chunk) / (chunk[:-1] + 1e-10)
        hist, _ = np.histogram(returns, bins=10, density=True)
        hist = hist + 1e-10
        entropy = -np.sum(hist * np.log(hist + 1e-10))
        result.append(entropy)
    return pd.Series(result, index=series.index)

def calc_fourier_strength(series, window=WINDOW_SHORT):
    """قوة الدورات الخفية"""
    result = []
    for i in range(len(series)):
        if i < window:
            result.append(0.0)
            continue
        chunk = series.iloc[i-window:i].values
        chunk = chunk - np.mean(chunk)
        fft_vals = np.abs(fft(chunk))
        strength = np.max(fft_vals[1:window//2]) / (np.mean(fft_vals[1:window//2]) + 1e-10)
        result.append(float(strength))
    return pd.Series(result, index=series.index)

def calc_volume_ratio(volume, window=WINDOW_SHORT):
    """نسبة الحجم الحالي للمتوسط"""
    avg = volume.rolling(window).mean()
    return volume / (avg + 1e-10)

def calc_close_position(high, low, close):
    """موقع الإغلاق في نطاق الشمعة"""
    return (close - low) / (high - low + 1e-10)

def calc_price_range(high, low, close):
    """نطاق الشمعة نسبة للسعر"""
    return (high - low) / (close + 1e-10)

# ══════════════════════════════
# كشف حالة السوق (Regime)
# ══════════════════════════════
def detect_regime(df, window=WINDOW_LONG):
    """
    trending — السوق في اتجاه واضح
    ranging — السوق هادي بين مستويين
    volatile — السوق متقلب وخطير
    """
    close = df["close"]
    returns = close.pct_change()
    
    vol = returns.rolling(window).std()
    vol_mean = vol.rolling(window * 2).mean()
    trend = abs(close.rolling(window).mean().pct_change(10))
    
    regimes = []
    for i in range(len(close)):
        if i < window * 2:
            regimes.append("ranging")
            continue
        
        v = vol.iloc[i]
        vm = vol_mean.iloc[i]
        t = trend.iloc[i]
        
        if v > vm * 2:
            regimes.append("volatile")
        elif t > 0.005:
            regimes.append("trending")
        else:
            regimes.append("ranging")
    
    return pd.Series(regimes, index=df.index)

# ══════════════════════════════
# استخراج كل الـ Features
# ══════════════════════════════
def extract_features(df, prefix=""):
    """
    يأخذ DataFrame فيه: timestamp, open, high, low, close, volume
    يرجع DataFrame فيه كل الـ features
    """
    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    
    p = prefix + "_" if prefix else ""
    
    # Z-Score
    df[f"{p}zscore_20"] = calc_zscore(close, 20)
    df[f"{p}zscore_50"] = calc_zscore(close, 50)
    
    # Mean Reversion
    df[f"{p}mean_rev_20"] = calc_mean_reversion(close, 20)
    df[f"{p}mean_rev_50"] = calc_mean_reversion(close, 50)
    
    # Momentum
    df[f"{p}momentum_5"] = calc_momentum(close, 5)
    df[f"{p}momentum_10"] = calc_momentum(close, 10)
    df[f"{p}momentum_20"] = calc_momentum(close, 20)
    
    # Volatility
    df[f"{p}volatility_20"] = calc_volatility(close, 20)
    df[f"{p}vol_ratio"] = calc_volume_ratio(volume, 20)
    
    # Price Structure
    df[f"{p}close_position"] = calc_close_position(high, low, close)
    df[f"{p}price_range"] = calc_price_range(high, low, close)
    
    # Advanced
    df[f"{p}autocorr"] = calc_autocorrelation(close, lag=1, window=20)
    df[f"{p}entropy"] = calc_entropy(close, window=20)
    df[f"{p}fourier"] = calc_fourier_strength(close, window=20)
    
    # Returns
    df[f"{p}returns"] = close.pct_change()
    df[f"{p}returns_5"] = close.pct_change(5)
    
    # Regime
    df[f"{p}regime"] = detect_regime(df)
    
    # تنظيف القيم الفارغة
    df = df.fillna(0)
    
    return df

# ══════════════════════════════
# استخراج Features لعملة كاملة (1m + 5m)
# ══════════════════════════════
def extract_all_features(symbol_data):
    """
    symbol_data = {"1m": df_1m, "5m": df_5m}
    يرجع DataFrame مدموج فيه features الفريمين
    """
    df_1m = symbol_data.get("1m")
    df_5m = symbol_data.get("5m")
    
    if df_1m is None or df_1m.empty:
        return None
    
    # استخراج features لكل فريم
    df_1m = extract_features(df_1m, prefix="1m")
    
    if df_5m is not None and not df_5m.empty:
        df_5m = extract_features(df_5m, prefix="5m")
        
        # أخذ آخر قيم 5m ودمجها مع 1m
        last_5m = df_5m.iloc[-1]
        for col in df_5m.columns:
            if col.startswith("5m_"):
                df_1m[col] = last_5m[col]
    
    return df_1m

# ══════════════════════════════
# أسماء الـ Features
# ══════════════════════════════
FEATURE_NAMES_1M = [
    "1m_zscore_20", "1m_zscore_50",
    "1m_mean_rev_20", "1m_mean_rev_50",
    "1m_momentum_5", "1m_momentum_10", "1m_momentum_20",
    "1m_volatility_20", "1m_vol_ratio",
    "1m_close_position", "1m_price_range",
    "1m_autocorr", "1m_entropy", "1m_fourier",
    "1m_returns", "1m_returns_5",
]

FEATURE_NAMES_5M = [
    "5m_zscore_20", "5m_zscore_50",
    "5m_mean_rev_20", "5m_mean_rev_50",
    "5m_momentum_5", "5m_momentum_10", "5m_momentum_20",
    "5m_volatility_20", "5m_vol_ratio",
    "5m_close_position", "5m_price_range",
    "5m_autocorr", "5m_entropy", "5m_fourier",
    "5m_returns", "5m_returns_5",
]

ALL_FEATURES = FEATURE_NAMES_1M + FEATURE_NAMES_5M

if __name__ == "__main__":
    print(f"✅ Features جاهزة: {len(ALL_FEATURES)} feature")
    for f in ALL_FEATURES:
        print(f" {f}")

