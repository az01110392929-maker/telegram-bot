import os
import asyncio
import logging
import ccxt.async_support as ccxt

# إعداد السجلات الهندسية لتوثيق وتتبع كل جزء من رأس المال بدقة فائقة
logging.basicConfig(
    format='%(asctime)s | [OKX-PROTECTION-BOT] | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)
logger = logging.getLogger("MaxProtectionTraderOKX")

class MaxProtectionTradingBotOKX:
    def __init__(self):
        self.api_key = os.getenv('OKX_API_KEY')
        self.api_secret = os.getenv('OKX_SECRET_KEY')
        self.passphrase = os.getenv('OKX_PASSPHRASE')
        
        # رموز التداول في OKX تكون عادة بصيغة BTC/USDT:USDT (للعقود أو الفوري حسب الإعداد)
        self.symbol = 'BTC/USDT'
        self.trade_amount_usdt = 11.0  # قيمة الصفقة
        self.poll_interval = 20  # فترة الفحص المنتظم
        
        # حماية صارمة لرأس المال
        self.in_position = False
        self.entry_price = 0.0
        self.take_profit_target = 0.015  # 1.5% ربح
        self.stop_loss_limit = 0.004     # 0.4% وقف خسارة

    async def get_available_balance(self, exchange: ccxt.okx):
        """فحص رصيد الـ USDT المتاح للتداول بأمان تام"""
        try:
            balance = await exchange.fetch_balance()
            free_usdt = balance['USDT']['free'] if 'USDT' in balance and 'free' in balance['USDT'] else 0.0
            return float(free_usdt)
        except Exception as e:
            logger.error(f"خطأ في قراءة الرصيد الفوري من OKX: {e}")
            return 0.0

    def calculate_rsi(self, closes, period=14):
        """حساب مؤشر القوة النسبية RSI بدقة هندسية عالية"""
        if len(closes) < period + 1:
            return 50.0
        
        gains, losses = [], []
        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
                
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
            
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    async def run_protected_strategy(self, exchange: ccxt.okx):
        logger.info("تم تفعيل النسخة القصوى لحماية الأصول وإدارة المخاطر على OKX بحذر شديد...")

        while True:
            try:
                logger.info("🔍 [OKX-Scanner] جاري فحص السوق وحركة الأسعار والمؤشرات الآن...")

                # 1. جلب السعر الحالي
                ticker = await exchange.fetch_ticker(self.symbol)
                current_price = float(ticker['last'])

                # 2. فحص الرصيد المتوفر
                balance = await self.get_available_balance(exchange)

                # 3. جلب الشمعات السعرية (1 دقيقة)
                ohlcv = await exchange.fetch_ohlcv(self.symbol, timeframe='1m', limit=40)
                closes = [float(entry[4]) for entry in ohlcv]
                rsi = self.calculate_rsi(closes)
                
                # حساب المتوسط المتحرك البسيط قصير المدى
                sma_20 = sum(closes[-20:]) / 20

                logger.info(f"📊 [حالة السوق] السعر: {current_price} | المتوسط (SMA20): {sma_20:.2f} | RSI: {rsi:.2f} | الرصيد المتاح: {balance:.2f} USDT")

                # 4. إدارة الصفقة المفتوحة وحمايتها لحظياً
                if self.in_position:
                    price_diff = (current_price - self.entry_price) / self.entry_price
                    logger.info(f"مراقبة صفقة نشطة. نسبة التغير الحالية: {price_diff * 100:.2f}%")

                    # جني الأرباح الآلي
                    if price_diff >= self.take_profit_target:
                        logger.info("🎯 هدف الربح تحقق بنجاح! جاري إرسال أمر بيع فوري لجني الأرباح...")
                        amount_to_sell = self.trade_amount_usdt / current_price
                        await exchange.create_market_sell_order(self.symbol, amount_to_sell)
                        self.in_position = False
                        logger.info("تم إغلاق الصفقة وتأمين الأرباح بنجاح.")

                    # وقف الخسارة الفوري
                    elif price_diff <= -self.stop_loss_limit:
                        logger.warning("🛡️ تنبيه حماية رأس المال: تراجع السعر بنسبة وقف الخسارة، جاري التخارج الفوري...")
                        amount_to_sell = self.trade_amount_usdt / current_price
                        await exchange.create_market_sell_order(self.symbol, amount_to_sell)
                        self.in_position = False
                        logger.warning("تم إغلاق الصفقة لحماية الرصيد الأساسي بالكامل.")

                # 5. شروط الدخول الحذرة والآمنة
                elif not self.in_position and balance >= self.trade_amount_usdt:
                    if rsi < 28.0 and current_price >= (sma_20 * 0.997):
                        logger.info(f"🔥 فرصة استثنائية مؤكدة (RSI: {rsi:.2f}). جاري تنفيذ أمر شراء فوري...")
                        # حساب الكمية المطلوبة بالعملة الأساسية بناءً على مبلغ الـ USDT
                        amount_to_buy = self.trade_amount_usdt / current_price
                        await exchange.create_market_buy_order(self.symbol, amount_to_buy)
                        self.entry_price = current_price
                        self.in_position = True
                        logger.info(f"تم تنفيذ الشراء بنجاح عند سعر أساسي: {self.entry_price}")
                    else:
                        logger.info("💤 السوق لا يوفر فرصة آمنة 100% الآن، البوت يفضل الاحتفاظ بالكاش...")
                else:
                    logger.warning("⚠️ الرصيد المتاح لا يغطي الحد الأدنى للصفقة الآمنة حالياً.")

                await asyncio.sleep(self.poll_interval)

            except ccxt.NetworkError as e:
                logger.warning(f"مشكلة اتصال مؤقتة بالشبكة مع OKX: {e}")
                await asyncio.sleep(20)
            except ccxt.ExchangeError as e:
                logger.warning(f"خطأ من منصة OKX API: {e}")
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"خطأ غير متوقع في محرك التداول الآمن: {e}")
                await asyncio.sleep(30)

    async def main(self):
        if not self.api_key or not self.api_secret or not self.passphrase:
            logger.critical("مفاتيح OKX أو كلمة المرور (Passphrase) مفقودة تماماً في متغيرات البيئة!")
            return

        logger.info("جاري تهيئة الاتصال بمنصة OKX...")
        exchange = ccxt.okx({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'password': self.passphrase,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'  # التحديد على التداول الفوري (Spot)
            }
        })

        try:
            # التحقق من الاتصال وصلاحيات الحساب
            await exchange.load_markets()
            logger.info("تم التحقق من مفاتيح OKX والاتصال بنجاح تام!")
            try:
                await self.run_protected_strategy(exchange)
            finally:
                await exchange.close()
        except ccxt.AuthenticationError as e:
            logger.critical(f"❌ رفضت OKX المفاتيح أو كلمة المرور: {e}")
            logger.critical("تأكد من صحة الـ API Key والـ Secret Key وعبارة المرور (Passphrase) ومن عدم وجود مسافات.")
        except Exception as e:
            logger.critical(f"خطأ حرج في تهيئة العميل مع OKX: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(MaxProtectionTradingBotOKX().main())
    except KeyboardInterrupt:
        logger.info("تم إيقاف النظام الهندسي الآمن يدويًا.")
        
