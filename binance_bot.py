import os
import time
import logging
import requests
from binance.client import Client
from binance.exceptions import BinanceAPIException

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توكن بوت التداول الجديد الخاص بك
TELEGRAM_BOT_TOKEN = "8878316487:AAFDepJN7aESM1kVjB43JmxJdSi1NrwUbYE"

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)

def get_latest_chat_id():
    """جلب معرف الدردشة تلقائياً من آخر شخص تفاعل مع البوت"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("ok") and data.get("result"):
            # البحث عن أحدث رسالة قمت بإرسالها للبوت
            for update in reversed(data["result"]):
                if "message" in update:
                    return update["message"]["chat"]["id"]
    except Exception as e:
        logger.error(f"Error fetching chat id: {e}")
    return None

def send_telegram_message(message):
    chat_id = get_latest_chat_id()
    if not chat_id:
        logger.warning("No chat_id found! Please send a message to the bot on Telegram first.")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            logger.error(f"Failed to send telegram message: {response.text}")
        else:
            logger.info("Telegram message sent successfully!")
    except Exception as e:
        logger.error(f"Error sending telegram message: {e}")

def check_market_and_trade():
    symbol = "BTCUSDT"
    target_usdt_amount = 11.0
    
    logger.info("Starting Binance market monitoring loop...")
    # محاولة إرسال رسالة ترحيبية أول ما يشتغل البوت
    send_telegram_message("🚀 *تم تفعيل بوت التداول بنجاح!\nالبوت يعمل الآن ويراقب السوق من أجلك.*")

    while True:
        try:
            klines = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1HOUR, limit=50)
            closes = [float(entry[4]) for entry in klines]
            
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

            if rsi < 28:
                account = client.get_account()
                usdt_balance = 0.0
                for balance in account['balances']:
                    if balance['asset'] == 'USDT':
                        usdt_balance = float(balance['free'])
                        break
                
                if usdt_balance >= target_usdt_amount:
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
                    send_telegram_message(success_msg)
                else:
                    logger.warning(f"RSI condition met, but insufficient USDT balance: {usdt_balance}")
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in trading loop: {e}")
        
        time.sleep(900)

if __name__ == "__main__":
    check_market_and_trade()
    
