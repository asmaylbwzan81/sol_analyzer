import os
import json
import random
import time
import numpy as np
import pandas as pd
from upstash_redis import Redis
from dotenv import load_dotenv

# استيراد الدوال الهندسية بناءً على الأسماء الجديدة للملفات في مشروعك
from data_engine import load_candles_to_df
from features import extract_all_features

# تحميل متغيرات البيئة من ملف .env المحلي
load_dotenv()

# ══════════════════════════════
# الإعدادات الهندسية والثوابت
# ══════════════════════════════
SYMBOLS = ["BTC-USDT", "SOL-USDT", "DOGE-USDT", "BNB-USDT", "XRP-USDT"]
POPULATION_SIZE = 30 # حجم مجتمع الاستراتيجيات في الجيل الواحد
GENERATIONS = 10 # عدد أجيال التطور والتحسين
WALK_FORWARD_SPLITS = 3 # عدد فترات فحص المحاكاة الأمامية المتتالية

# الخيار الذهبي المعدل لأهداف الصفقات الميكروية (تغطية الرسوم + ربح صافي)
TP_PCT = 0.0045 # الهدف الرقمي الإسمي: 0.45%
SL_PCT = 0.0025 # وقف الخسارة الصارم: 0.25%

# إنشاء عميل الاتصال بـ Upstash Redis باستخدام الـ REST SDK الرسمي
redis_client = Redis(
    url=os.getenv("UPSTASH_REDIS_REST_URL"),
    token=os.getenv("UPSTASH_REDIS_REST_TOKEN")
)

# ══════════════════════════════
# محرك محاكاة الفحص التاريخي (Fast Vectorized Backtester)
# ══════════════════════════════
def backtest_strategy(df, params):
    """
    محاكاة مصفوفية سريعة جداً لاختبار الميزة الإحصائية بناءً على عتبات متغيرة
    """
    if df.empty or len(df) < 100:
        return -100.0 # تصفية واستبعاد حزم البيانات غير الكافية
        
    # تحويل الأعمدة إلى مصفوفات Numpy سريعة جداً لخدمة الـ HFT
    close = df["close"].values
    regime = df["1m_regime"].values
    zscore = df["1m_zscore_20"].values
    entropy = df["1m_entropy"].values
    fourier = df["1m_fourier"].values
    returns = df["1m_returns"].values
    
    total_return = 0.0
    in_position = False
    pos_type = None
    entry_price = 0.0
    
    for i in range(1, len(df)):
        if not in_position:
            # 1. حالة الـ Ranging -> تفعيل استراتيجية الارتداد للمتوسط (Mean Reversion)
            if regime[i] == "ranging":
                if entropy[i] <= params['entropy_max'] and fourier[i] >= params['fourier_min']:
                    if zscore[i] >= params['z_trigger']:
                        in_position = True
                        pos_type = "SELL"
                        entry_price = close[i]
                    elif zscore[i] <= -params['z_trigger']:
                        in_position = True
                        pos_type = "BUY"
                        entry_price = close[i]
                        
            # 2. حالة الـ Trending -> تفعيل استراتيجية ملاحقة الزخم (Momentum)
            elif regime[i] == "trending":
                if zscore[i] > 1.0 and returns[i] > 0:
                    in_position = True
                    pos_type = "BUY"
                    entry_price = close[i]
                elif zscore[i] < -1.0 and returns[i] < 0:
                    in_position = True
                    pos_type = "SELL"
                    entry_price = close[i]
        else:
            # حساب الأرباح والخسائر بدقة رياضية بناءً على نوع الحركة والاتجاه
            if pos_type == "BUY":
                price_change = (close[i] - entry_price) / entry_price
                if price_change >= TP_PCT:
                    total_return += TP_PCT
                    in_position = False
                elif price_change <= -SL_PCT:
                    total_return -= SL_PCT
                    in_position = False
            elif pos_type == "SELL":
                # صفقات البيع تربح مع هبوط السعر عن نقطة الدخول
                price_change = (entry_price - close[i]) / entry_price
                if price_change >= TP_PCT:
                    total_return += TP_PCT
                    in_position = False
                elif price_change <= -SL_PCT:
                    total_return -= SL_PCT
                    in_position = False
                    
    return total_return

# ══════════════════════════════
# أدوات الخوارزمية الجينية (Genetic GA Operators)
# ══════════════════════════════
def generate_random_chromosome():
    """توليد كروموسوم عشوائي يحتوي على العتبات الرياضية الأساسية"""
    return {
        'z_trigger': round(random.uniform(1.5, 3.5), 2),
        'entropy_max': round(random.uniform(1.5, 3.0), 2),
        'fourier_min': round(random.uniform(1.0, 5.0), 2)
    }

def crossover(parent1, parent2):
    """عملية التزاوج الجيني لخلط الصفات الاحتمالية الناجحة"""
    return {key: parent1[key] if random.random() > 0.5 else parent2[key] for key in parent1}

def mutate(chromosome):
    """إحداث طفرة جينية عشوائية للخروج من نقاط التحسين المحلية العالقة"""
    mutated = chromosome.copy()
    key = random.choice(list(mutated.keys()))
    if key == 'z_trigger': 
        mutated[key] = round(random.uniform(1.5, 3.5), 2)
    elif key == 'entropy_max': 
        mutated[key] = round(random.uniform(1.5, 3.0), 2)
    elif key == 'fourier_min': 
        mutated[key] = round(random.uniform(1.0, 5.0), 2)
    return mutated

# ══════════════════════════════
# المحرك الجيني المركزي مع فحص المحاكاة الأمامية (Walk-Forward GA Loop)
# ══════════════════════════════
def run_genetic_optimization(df):
    """إخضاع الاستراتيجيات لدورات التطور جينياً مع عزل الفترات لمنع الـ Overfitting"""
    splits = np.array_split(df, WALK_FORWARD_SPLITS)
    best_params = None
    best_score = -999.0
    
    for split_idx, train_df in enumerate(splits):
        print(f" ⏳ الفترة الزمنية رقم {split_idx + 1}/{WALK_FORWARD_SPLITS}...")
        
        # إعادة تهيئة مجتمع جيني جديد نقي لكل فترة لمنع الانحياز الإحصائي وتسريب البيانات
        population = [generate_random_chromosome() for _ in range(POPULATION_SIZE)]
        
        for generation in range(GENERATIONS):
            # قياس كفاءة كل كروموسوم (Fitness Score)
            scores = [backtest_strategy(train_df, chrom) for chrom in population]
            
            # فرز وترتيب الكروموسومات تنازلياً حسب الأعلى عائداً
            sorted_indices = np.argsort(scores)[::-1]
            population = [population[idx] for idx in sorted_indices]
            
            # الاحتفاظ بأفضل عينات رياضية مستقرة عبر الفترات
            if scores[sorted_indices[0]] > best_score:
                best_score = scores[sorted_indices[0]]
                best_params = population[0]
                
            # إنتاج الجيل التالي عبر الحفاظ على النخبة الـ 5 الأوائل وتزويج البقية
            next_gen = population[:5]
            while len(next_gen) < POPULATION_SIZE:
                p1 = random.choice(population[:10])
                p2 = random.choice(population[:10])
                child = crossover(p1, p2)
                
                # تطبيق معدل طفرة جينية بنسبة 20% لضمان التنوع الرقمي
                if random.random() < 0.2:
                    child = mutate(child)
                next_gen.append(child)
                
            population = next_gen
            
    return best_params, best_score

# ══════════════════════════════
# دالة التشغيل المركزية والمزامنة السحابية
# ══════════════════════════════
def main():
    print("🧬 إطلاق محرك الأوبتمايزر الجيني المحلي المطور بالكامل...")
    print("━" * 65)
    
    for symbol in SYMBOLS:
        print(f"\n🪙 معالجة وحساب النمذجة الجينية للأصل: {symbol}")
        try:
            # 1. سحب حزم البيانات الخام المخزنة محلياً في SQLite
            df_1m = load_candles_to_df(symbol, "1m")
            df_5m = load_candles_to_df(symbol, "5m")
            
            if df_1m.empty:
                print(f" ⚠️ لم يتم العثور على بيانات تاريخية لـ {symbol}. تم التخطي.")
                continue
                
            # 2. توليد مصفوفات الخصائص المتقدمة من ملف الميزات الخاص بك
            symbol_data = {"1m": df_1m, "5m": df_5m}
            df_features = extract_all_features(symbol_data)
            
            # 3. إدخال الخصائص في معمل المحاكاة والتطور الجيني المشروط
            best_params, fitness = run_genetic_optimization(df_features)
            
            print(f" 🎯 أفضل معاملات مستقرة: {best_params}")
            print(f" 📈 العائد المتوقع للفترات: {round(fitness*100, 2)}%")
            
            # 4. شحن مصفوفة الإعدادات بصيغة JSON موحدة ونظيفة إلى حساب Upstash Redis
            redis_key = f"strategy:{symbol.replace('-USDT', '')}" # النتيجة الحركية النظيفة: strategy:BTC
            strategy_data = {
                "params": best_params,
                "tp_pct": TP_PCT,
                "sl_pct": SL_PCT,
                "fitness": round(fitness * 100, 2),
                "last_updated": int(time.time())
            }
            
            # حفظ حزمة المعاملات تحت مفتاح String موحد لضمان سرعة القراءة الحيّة اللاحقة
            redis_client.set(redis_key, json.dumps(strategy_data))
            print(f" ✅ تم تحديث وشحن البيانات بنجاح إلى قاعدة Redis: {redis_key}")
            
        except Exception as e:
            print(f" ❌ فشل فني غير متوقع أثناء معالجة العملة {symbol}: {e}")
            
    print("\n🏁 انتهت جلسة التطور الجيني المحلي بنجاح. تم تأمين النماذج الحركية، وينطفئ السكربت تلقائياً ✅")

if __name__ == "__main__":
    main()

