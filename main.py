import ccxt
import time
import math
import sys

# ضع بيانات الـ API الحقيقية وكلمة مرور الـ API (Passphrase) هنا بدقة
API_KEY = 'ضع_مفتاح_الـ_API_هنا'
SECRET_KEY = 'ضع_المفتاح_السري_هنا'
PASSWORD = 'ضع_كلمة_مرور_الـ_API_هنا'

# إعدادات الاتصال المباشر والآمن بمنصة OKX
exchange = ccxt.okx({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'password': PASSWORD,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

SYMBOLS = ['BTC/USDT', 'ETH/USDT']
BASE_MAX_ALLOCATION_PCT = 0.80
TRAILING_DROP_PCT = 0.002
DCA_THRESHOLD_PCT = 0.0015

def safe_api_call(func, *args, **kwargs):
    max_retries = 5
    delay = 2
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"تنبيه اتصال (محاولة {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise e
            time.sleep(delay)
            delay *= 2

def get_balance(currency='USDT'):
    try:
        balance = safe_api_call(exchange.fetch_balance)
        return float(balance['free'].get(currency, 0))
    except Exception as e:
        print(f"خطأ في جلب الرصيد: {e}")
        return 0.0

def get_market_price(symbol):
    try:
        ticker = safe_api_call(exchange.fetch_ticker, symbol)
        return float(ticker['last'])
    except Exception as e:
        print(f"خطأ في جلب سعر {symbol}: {e}")
        return None

def institutional_market_analysis(symbol):
    try:
        order_book = safe_api_call(exchange.fetch_order_book, symbol, limit=50)
        bids = order_book['bids']
        asks = order_book['asks']
        
        bids_top_vol = sum([b[1] for b in bids[:15]])
        asks_top_vol = sum([a[1] for a in asks[:15]])
        
        if asks_top_vol > 0 and (bids_top_vol / asks_top_vol) < 1.2:
            return None, None, None, None

        ohlcv_1h = safe_api_call(exchange.fetch_ohlcv, symbol, timeframe='1h', limit=30)
        closes_1h = [c[4] for c in ohlcv_1h]
        ema_1h = sum(closes_1h) / len(closes_1h)
        if closes_1h[-1] < ema_1h:
            return None, None, None, None

        ohlcv_15m = safe_api_call(exchange.fetch_ohlcv, symbol, timeframe='15m', limit=50)
        if not ohlcv_15m or len(ohlcv_15m) < 50:
            return None, None, None, None

        closes_15m = [c[4] for c in ohlcv_15m]
        ema_15m = sum(closes_15m) / len(closes_15m)
        current_price = closes_15m[-1]

        if current_price < ema_15m:
            return None, None, None, None

        highs = [c[2] for c in ohlcv_15m[-14:]]
        lows = [c[3] for c in ohlcv_15m[-14:]]
        tr_list = [highs[i] - lows[i] for i in range(len(highs))]
        avg_atr = sum(tr_list) / len(tr_list)
        
        volatility_ratio = avg_atr / current_price
        if volatility_ratio < 0.0005:
            return None, None, None, None

        dynamic_tp_pct = max(0.008, min(0.015, volatility_ratio * 1.5))
        dynamic_sl_pct = 0.0025
        strength_score = min(1.0, (bids_top_vol / (asks_top_vol + 1e-8)) / 2.0)

        return True, dynamic_tp_pct, dynamic_sl_pct, strength_score

    except Exception as e:
        print(f"خطأ في التحليل المؤسسي لـ {symbol}: {e}")
        return None, None, None, None

def place_order(symbol, amount_usd, price):
    try:
        amount = amount_usd / price
        market = safe_api_call(exchange.load_markets)
        precision = market[symbol]['precision']['amount']
        if isinstance(precision, float) or (isinstance(precision, int) and precision < 1):
            amount = round(amount, 6)
        else:
            amount = math.floor(amount * (10 ** precision)) / (10 ** precision)

        print(f"تنفيذ صفقة مؤسسية لـ {symbol} بقيمة {amount_usd:.2f}$ (الكمية: {amount}) بسعر {price}")
        order = safe_api_call(exchange.create_market_buy_order, symbol, amount)
        return order
    except Exception as e:
        print(f"فشل تنفيذ أمر الشراء على {symbol}: {e}")
        return None

def monitor_trade(symbol, initial_entry_price, initial_amount, target_tp_pct, target_sl_pct):
    current_entry_price = initial_entry_price
    total_amount = initial_amount
    total_cost = initial_entry_price * initial_amount
    
    dca_used = False
    highest_price = initial_entry_price
    trailing_active = False

    print(f"بدء المراقبة لـ {symbol} | الدخول: {initial_entry_price}")

    while True:
        try:
            current_price = get_market_price(symbol)
            if not current_price:
                time.sleep(5)
                continue

            tp_price = current_entry_price * (1 + target_tp_pct)
            sl_price = current_entry_price * (1 - target_sl_pct)

            if not dca_used and current_price <= (current_entry_price * (1 - DCA_THRESHOLD_PCT)):
                print(f"تفعيل التعافي الذكي (DCA) لـ {symbol}...")
                balance_usdt = get_balance('USDT')
                dca_amount_usd = min(balance_usdt * 0.4, 30.0)
                
                if dca_amount_usd >= 10.0:
                    dca_order = place_order(symbol, dca_amount_usd, current_price)
                    if dca_order:
                        dca_filled_price = float(dca_order.get('average', current_price) or current_price)
                        dca_filled_amount = float(dca_order.get('filled', 0))
                        total_cost += (dca_filled_price * dca_filled_amount)
                        total_amount += dca_filled_amount
                        current_entry_price = total_cost / total_amount
                        dca_used = True
                        print(f"متوسط السعر الجديد: {current_entry_price}")

            if current_price <= sl_price:
                print(f"تفعيل وقف الخسارة لـ {symbol}.")
                safe_api_call(exchange.create_market_sell_order, symbol, total_amount)
                break

            if current_price > highest_price:
                highest_price = current_price

            if not trailing_active and current_price >= tp_price:
                trailing_active = True
                print(f"تفعيل تتبع الأرباح لـ {symbol} عند قمة: {highest_price}")

            if trailing_active:
                drop_threshold = highest_price * (1 - TRAILING_DROP_PCT)
                if current_price <= drop_threshold:
                    print(f"جني الأرباح القصوى لـ {symbol}!")
                    safe_api_call(exchange.create_market_sell_order, symbol, total_amount)
                    break

            time.sleep(10)
        except Exception as e:
            print(f"خطأ أثناء المراقبة: {e}")
            time.sleep(5)

def run_bot():
    print("=== تشغيل البوت مع التثبيت اليدوي للبيانات ==Raise ===")
    
    while True:
        try:
            usdt_balance = get_balance('USDT')
            print(f"رصيد الـ USDT المتاح: {usdt_balance}$")

            for symbol in SYMBOLS:
                is_valid, dyn_tp, dyn_sl, strength_score = institutional_market_analysis(symbol)
                
                if not is_valid:
                    print(f"شروط السوق لـ {symbol} لا تلبي المعايير حالياً. التخطي.")
                    continue

                adaptive_trade_amount = usdt_balance * BASE_MAX_ALLOCATION_PCT * strength_score

                if adaptive_trade_amount >= 10.0:
                    current_price = get_market_price(symbol)
                    if not current_price:
                        continue

                    print(f"شروط مؤسسية متطابقة لـ {symbol}. تنفيذ بقيمة: {adaptive_trade_amount:.2f}$")
                    order = place_order(symbol, adaptive_trade_amount, current_price)

                    if order:
                        filled_price = float(order.get('average', current_price) or current_price)
                        filled_amount = float(order.get('filled', 0))
                        monitor_trade(symbol, filled_price, filled_amount, dyn_tp, dyn_sl)
                        break
                else:
                    print(f"الرصيد المتاح لـ {symbol} أقل من الحد الأدنى (10$).")

            time.sleep(30)
        except Exception as e:
            print(f"خطأ رئيسي: {e}")
            time.sleep(10)

if __name__ == '__main__':
    run_bot()
    
