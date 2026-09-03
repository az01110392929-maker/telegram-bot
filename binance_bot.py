import os
import time
import logging
import requests
from binance.client import Client
from binance.exceptions import BinanceAPIException

# إعداد السجلات لمتابعة حالة البوت بدقة
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# جلب المفاتيح والإعدادات بأمان من متغيرات البيئة في Railway
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
# معرف الدردشة الخاص بك لضمان وصول رسائل التداول لك وحدك
MY_CHAT_ID = "5721549115"

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

# إعداد عميل باينانس (تداول حقيقي)
client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)

def send_telegram_message(message):
    """إرسال إشعار فوري إلى حسابك الشخصي على تلجرام"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Telegram BOT_TOKEN is missing!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": MY_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            logger.error(f"Failed to send telegram message: {response.text}")
    except Exception as e:
        logger.error(f"Error sending telegram message: {e}")

def check_market_and_trade():
    """حلقة مراقبة السوق وتنفيذ الصفقات بأمان بناءً على استراتيجية الـ RSI"""
    symbol = "BTCUSDT"
    target_usdt_amount = 11.0  # الالتزام بالحد الأدنى للصفقة على باينانس
    
    logger.info("Starting Binance market monitoring loop...")
    send_telegram_message("🚀 *تم تفعيل بوت التداول بنجاح!*\nالبوت يعمل الآن في الخلفية ويراقب السوق من أجلك.")

    while True:
        try:
            # جلب أسعار الإغلاق التاريخية لحساب مؤشر الـ RSI
            klines = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1HOUR, limit=50)
            closes = [float(entry[4]) for entry in klines]
            
            # حساب مبسط لمؤشر القوة النسبية RSI (14 فترة)
            gains = []
            losses = []
            for i in range(1, len(closes)):
                diff = closes[i] - closes[i-1]
                if diff >= 0:
                    gains.append(diff)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(diff))
            
            avg_gain = sum(gains[-14:]) / 14
            avg_loss = sum(losses[-14:]) / 14
            
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            
            current_price = closes[-1]
            logger.info(f"Checked {symbol} - Current Price: {current_price} | RSI: {rsi:.2f}")

            # شرط الدخول في صفقة شراء (إذا هبط المؤشر تحت 28 ووجدت الفرصة آمنة)
            if rsi < 28:
                # التحقق من رصيد الـ USDT المتاح في المحفظة الفورية
                account = client.get_account()
                usdt_balance = 0.0
                for balance in account['balances']:
                    if balance['asset'] == 'USDT':
                        usdt_balance = float(balance['free'])
                        break
                
                logger.info(f"RSI is low ({rsi:.2f}). Checking USDT balance: {usdt_balance}")
                
                if usdt_balance >= target_usdt_amount:
                    # تنفيذ أمر الشراء الفوري (Market Buy)
                    order = client.order_market_buy(
                        symbol=symbol,
                        quoteOrderQty=target_usdt_amount
                    )
                    success_msg = (
                        f"🎯 *تم تنفيذ صفقة شراء بنجاح!*\n"
                        f"• العملة: {symbol}\n"
                        f"• القيمة: {target_usdt_amount} USDT\n"
                        f"• مؤشر RSI: {rsi:.2f}\n"
                        f"• السعر الحالي: {current_price}"
                    )
                    logger.info(success_msg)
                    send_telegram_message(success_msg)
                else:
                    logger.warning(f"RSI condition met, but insufficient USDT balance: {usdt_balance}")
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in trading loop: {e}")
        
        # الانتظار لمدة 15 دقيقة قبل إعادة فحص السوق لتوفير الموارد
        time.sleep(900)

if __name__ == "__main__":
    check_market_and_trade()
    
