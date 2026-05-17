import os
import json
import asyncio
import time
import aiohttp
import pandas as pd
from upstash_redis.asyncio import Redis # التعديل الجوهري: استيراد النسخة غير المتزامنة
from dotenv import load_dotenv

# استيراد محرك الخصائص الفيزيائية والرياضية المشترك
from features import extract_all_features

# تحميل بيئة الأمان السحابية
load_dotenv()

# ══════════════════════════════
# الإعدادات الهندسية والثوابت
# ══════════════════════════════
SYMBOLS = ["BTC-USDT", "SOL-USDT", "DOGE-USDT", "BNB-USDT", "XRP-USDT"]
BINGX_URL = "https://open-api.bingx.com/openApi/swap/v2/quote/klines"

# إنشاء العميل غير المتزامن بشكل صحيح
redis_client = Redis(
    url=os.getenv("UPSTASH_REDIS_REST_URL"),
    token=os.getenv("UPSTASH_REDIS_REST_TOKEN")
)

# ══════════════════════════════
# جلب البيانات الحية
# ══════════════════════════════
async def fetch_candles_async(session, symbol, interval, limit=100):
    """جلب الشموع الحية لحظياً من BingX بدون حظر السيرفر"""
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    try:
        async with session.get(BINGX_URL, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                candles = data.get("data", [])
                if not candles:
                    return pd.DataFrame()

                # بناء الـ DataFrame مع ضمان تحويل الحروف الصغيرة لأسماء الأعمدة لملف الـ features
                df = pd.DataFrame([{
                    "timestamp": int(c.get("time", 0)),
                    "open": float(c.get("open", 0)),
                    "high": float(c.get("high", 0)),
                    "low": float(c.get("low", 0)),
                    "close": float(c.get("close", 0)),
                    "volume": float(c.get("volume", 0))
                } for c in candles])

                # الترتيب الزمني الصحيح من الأقدم للأحدث كما يتوقعه الموديل
                return df.sort_values("timestamp").reset_index(drop=True)
            return pd.DataFrame()
    except Exception as e:
        print(f" ❌ خطأ جلب {symbol} ({interval}): {e}")
        return pd.DataFrame()

# ══════════════════════════════
# فحص وإرسال الإشارة
# ══════════════════════════════
async def process_symbol(session, symbol):
    try:
        # 1. قراءة الاستراتيجية من Redis — مع استخدام await الإلزامية هنا
        redis_key = f"strategy:{symbol.replace('-USDT', '')}"
        strategy_raw = await redis_client.get(redis_key)

        if not strategy_raw:
            return

        # تأمين القراءة وفك ترميز النصوص
        if isinstance(strategy_raw, str):
            strategy_data = json.loads(strategy_raw)
        else:
            strategy_data = strategy_raw
            
        params = strategy_data["params"]
        tp_pct = float(strategy_data["tp_pct"])
        sl_pct = float(strategy_data["sl_pct"])

        # 2. جلب البيانات بالتوازي بشكل غير حاصر للسيرفر
        df_1m, df_5m = await asyncio.gather(
            fetch_candles_async(session, symbol, "1m"),
            fetch_candles_async(session, symbol, "5m")
        )

        if df_1m.empty or df_5m.empty or len(df_1m) < 50:
            return

        # 3. استخراج الميزات الإحصائية
        df_features = extract_all_features({"1m": df_1m, "5m": df_5m})

        if df_features is None or df_features.empty:
            return

        # التقاط آخر سطر مغلق بالكامل
        last_row = df_features.iloc[-1]

        current_close = float(last_row["close"])
        current_regime = str(last_row["1m_regime"])
        current_zscore = float(last_row["1m_zscore_20"])
        current_entropy = float(last_row["1m_entropy"])
        current_fourier = float(last_row["1m_fourier"])
        current_returns = float(last_row["1m_returns"])

        signal_direction = None

        # أ. استراتيجية الارتداد للمتوسط (Mean Reversion)
        if current_regime == "ranging":
            if current_entropy <= params['entropy_max'] and current_fourier >= params['fourier_min']:
                if current_zscore >= params['z_trigger']:
                    signal_direction = "SELL"
                elif current_zscore <= -params['z_trigger']:
                    signal_direction = "BUY"

        # ب. استراتيجية ملاحقة الزخم الصارم (Momentum)
        elif current_regime == "trending":
            if current_zscore > 1.0 and current_returns > 0:
                signal_direction = "BUY"
            elif current_zscore < -1.0 and current_returns < 0:
                signal_direction = "SELL"

        # 4. إرسال الإشارة إلى Redis — مع استخدام await الإلزامية
        if signal_direction:
            tp_price = current_close * (1 + tp_pct) if signal_direction == "BUY" else current_close * (1 - tp_pct)
            sl_price = current_close * (1 - sl_pct) if signal_direction == "BUY" else current_close * (1 + sl_pct)

            signal_payload = {
                "symbol": symbol,
                "direction": signal_direction,
                "price": round(current_close, 4),
                "tp": round(tp_price, 4),
                "sl": round(sl_price, 4),
                "timestamp": int(time.time())
            }

            # كتابة الإشارة في طابور التنفيذ اللحظي بشكل غير متزامن
            await redis_client.set("signal:pending", json.dumps(signal_payload))
            print(f" 🎯 إشارة موثقة: {symbol} -> {signal_direction} | السعر: {current_close}")

    except Exception as e:
        print(f" ❌ خطأ معالجة {symbol}: {e}")

# ══════════════════════════════
# الحلقة الرئيسية 24/7
# ══════════════════════════════
async def main():
    print("🤖 بوت المراقبة الحية غير المتزامن شغال 24/7 على السيرفر...")
    print("━" * 60)

    async with aiohttp.ClientSession() as session:
        while True:
            start_time = time.time()

            # تشغيل معالجة كافة العملات بالتوازي لتفادي أي انزلاق زمني
            tasks = [process_symbol(session, symbol) for symbol in SYMBOLS]
            await asyncio.gather(*tasks)

            # النوم الحسابي الدقيق لانتظار الدقيقة القادمة
            elapsed = time.time() - start_time
            sleep_time = max(0, 60 - elapsed)
            await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    asyncio.run(main())

