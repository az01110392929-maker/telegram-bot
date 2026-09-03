import os
import time
import logging
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# إعداد السجل الاحترافي
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# جلب المتغيرات البيئية من Railway بأمان
BOT_TOKEN = os.getenv("BOT_TOKEN")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

BASE_URL = 'https://api.binance.com'

def fetch_binance_balance():
    """جلب الأرصدة الحقيقية من باينانس باستخدام توقيع HMAC SHA256 الآمن"""
    if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
        return "⚠️ مفاتيح باينانس غير مضبوطة في متغيرات البيئة!"
    
    endpoint = '/api/v3/account'
    timestamp = int(time.time() * 1000)
    params = {'timestamp': timestamp}
    
    query_string = urlencode(params)
    signature = hmac.new(
        BINANCE_SECRET_KEY.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params['signature'] = signature
    headers = {'X-MBX-APIKEY': BINANCE_API_KEY}
    
    try:
        response = requests.get(BASE_URL + endpoint, headers=headers, params=params, timeout=10)
        data = response.json()
        
        if 'balances' in data:
            active_assets = [b for b in data['balances'] if float(b['free']) > 0 or float(b['locked']) > 0]
            msg = "💰 **أرصدة حسابك النشطة في باينانس:**\n"
            for asset in active_assets[:10]:
                msg.endswith()
                msg += f"• `{asset['asset']}`: متاح ({float(asset['free'])})\n"
            return msg
        else:
            return f"❌ خطأ من باينانس: {data.get('msg', 'استجابة غير معروفة')}"
    except Exception as e:
        logger.error(f"خطأ في الاتصال بـ Binance API: {e}")
        return "❌ حدث خطأ في الاتصال بخوادم باينانس أثناء جلب الأرصدة."

def calculate_btc_rsi():
    """حساب مؤشر القوة النسبية RSI لعملة BTC على فريم 1ساعة"""
    try:
        endpoint = '/api/v3/klines'
        params = {'symbol': 'BTCUSDT', 'interval': '1h', 'limit': 50}
        response = requests.get(BASE_URL + endpoint, params=params, timeout=10)
        candles = response.json()
        
        if not isinstance(candles, list) or len(candles) < 15:
            return "⚠️ بيانات الشموع غير كافية لحساب RSI حالياً."
        
        closes = [float(c[4]) for c in candles]
        gains, losses = [], []
        
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i-1]
            if diff >= 0:
                gains.append(diff)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(diff))
                
        # حساب متوسط أول 14 فترة
        avg_gain = sum(gains[:14]) / 14
        avg_loss = sum(losses[:14]) / 14
        
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
        current_price = closes[-1]
        return f"📊 **تحليل عملة BTCUSDT الفوري:**\n• السعر الحالي: `{current_price}`$\n• مؤشر RSI (1س): `{rsi:.2f}`\n\n" + \
               ("🔥 الوضع: تشبع شراء (Overbought)" if rsi > 70 else "❄️ الوضع: تشبع بيع (Oversold)" if rsi < 30 else "⚖️ الوضع: استقرار وسوق عرضي")
    except Exception as e:
        logger.error(f"خطأ في حساب RSI: {e}")
        return "❌ تعذر حساب مؤشر RSI حالياً بسبب خطأ في جلب بيانات السوق."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 **أهلاً بك يا محمود في بوت التداول الاحترافي المتقدم!**\n\n"
        "القائمة المتاحة:\n"
        "🔹 `/balance` - لجلب أرصدة محفظتك الحية من باينانس.\n"
        "🔹 `/rsi` - لفحص مؤشر RSI وسعر BTC اللحظي.\n"
        "🔹 `/status` - للتحقق من كفاءة سيرفر التشغيل المستقل."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 جاري التواصل المشفر مع محفظة باينانس...")
    result = fetch_binance_balance()
    await update.message.reply_text(result, parse_mode="Markdown")

async def rsi_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📉 جاري جلب الشموع اليابانية وحساب مؤشر RSI...")
    result = calculate_btc_rsi()
    await update.message.reply_text(result, parse_mode="Markdown")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🟢 السيرفر يعمل بكفاءة تامة على Railway ومستقل تماماً عن بوت المتجر.")

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN مفقود!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("rsi", rsi_cmd))
    app.add_handler(CommandHandler("status", status_cmd))

    logger.info("🚀 بوت التداول الاحترافي بدأ بالعمل بنجاح تام...")
    app.run_polling()

if __name__ == '__main__':
    main()
    
