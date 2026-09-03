import os
import asyncio
import logging
import ccxt.async_support as ccxt

# إعداد السجلات الهندسية لتوثيق وتتبع كل جزء من رأس المال بدقة فائقة
logging.basicConfig(
    format='%(asctime)s | [OKX-ADVANCED-BOT] | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)
logger = logging.getLogger("MaxProtectionTraderOKXAdvanced")

class MaxProtectionTradingBotOKX:
    def __init__(self):
        self.api_key = os.getenv('OKX_API_KEY')
        self.api_secret = os.getenv('OKX_SECRET_KEY')
        self.passphrase = os.getenv('OKX_PASSPHRASE')
        
        self.symbol = 'BTC/USDT'
        self.trade_amount_usdt = 11.0  # قيمة الصفقة
        self.poll_interval = 20  # فترة الفحص المنتظم
        
        # إعدادات الحماية والأرباح المتطورة
        self.in_position = False
        self.entry_price = 0.0
        self.highest_price = 0.0         # لتتبع أعلى سعر وصل له السعر بعد الشراء (للـ Trailing Stop)
        self.take_profit_target = 0.02   # 2% هدف ربح أساسي محسّن
        self.stop_loss_limit = 0.0035    # 0.35% وقف خسارة أولي صارم
        self.trailing_activation = 0.01  # تفعيل الوقف المتحرك إذا حقق السعر 1% ربح
        self.trailing_drop = 0.005       # السماح بتراجع قدره 0.5% فقط من القمة المحققة لحجز الأرباح

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
        logger.info("تم تفعيل النسخة المذكية والمطورة لحماية الأصول ومضاعفة الأرباح على OKX...")

        while True:
            try:
                logger.info("🔍 [OKX-Advanced-Scanner] جاري فحص السوق وحركة الأسعار والمؤشرات بدقة...")

                # 1. جلب السعر الحالي
                ticker = await exchange.fetch_ticker(self.symbol)
                current_price = float(ticker['last'])

                # 2. فحص الرصيد المتوفر
                balance = await self.get_available_balance(exchange)

                # 3. جلب الشمعات السعرية (1 دقيقة) - نطاق أوسع لحساب المؤشرات بدقة
                ohlcv = await exchange.fetch_ohlcv(self.symbol, timeframe='1m', limit=60)
                closes = [float(entry[4]) for entry in ohlcv]
                rsi = self.calculate_rsi(closes)
                
                # المتوسطات المتحركة لفلترة الاتجاه العام وضمان الأمان
                sma_20 = sum(closes[-20:]) / 20
                sma_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else sma_20

                logger.info(f"📊 [حالة السوق] السعر: {current_price} | SMA20: {sma_20:.2f} | SMA50: {sma_50:.2f} | RSI: {rsi:.2f} | الكاش: {balance:.2f}")

                # 4. إدارة الصفقة المفتوحة بالوقف المتحرك (Trailing Stop) وجني الأرباح
                if self.in_position:
                    price_diff = (current_price - self.entry_price) / self.entry_price
                    
                    # تحديث أعلى سعر وصل إليه السعر منذ الدخول
                    if current_price > self.highest_price:
                        self.highest_price = current_price

                    highest_diff = (self.highest_price - self.entry_price) / self.entry_price
                    logger.info(f"📈 صفقة نشطة. التغير الحالي: {price_diff * 100:.2f}% | أعلى قمة وصلت لها: {highest_diff * 100:.2f}%")

                    # أ. هدف الربح الثابت والمستهدف الكبير
                    if price_diff >= self.take_profit_target:
                        logger.info("🎯 هدف الربح الممتاز تحقق! جاري جني الأرباح فوريًا...")
                        amount_to_sell = self.trade_amount_usdt / current_price
                        await exchange.create_market_sell_order(self.symbol, amount_to_sell)
                        self.in_position = False
                        logger.info("✅ تم إغلاق الصفقة بنجاح وتأمين الأرباح الكبرى.")

                    # ب. نظام الوقف المتحرك الذكي (Trailing Stop): إذا صعد السعر ثم بدأ بالارتداد من القمة
                    elif highest_diff >= self.trailing_activation and current_price <= self.highest_price * (1 - self.trailing_drop):
                        logger.info(kf := f"🔒 تفعيل الوقف المتحرك (Trailing Stop)! تم جني الأرباح قبل انعكاس السوق من القمة...")
                        amount_to_sell = self.trade_amount_usdt / current_price
                        await exchange.create_market_sell_order(self.symbol, amount_to_sell)
                        self.in_position = False
                        logger.info("✅ تم الخروج بأمان تام مع المحافظة على الأرباح المحققة.")

                    # ج. وقف الخسارة الأولي الصارم جداً لحماية رأس المال
                    elif price_diff <= -self.stop_loss_limit:
                        logger.warning("🛡️ حماية رأس المال: تراجع السعر دون الحد المسموح، خروج فوري لحماية الكاش...")
                        amount_to_sell = self.trade_amount_usdt / current_price
                        await exchange.create_market_sell_order(self.symbol, amount_to_sell)
                        self.in_position = False
                        logger.warning("⚠️ تم إغلاق الصفقة على خسارة طفيفة جداً لحماية الأصول بالكامل.")

                # 5. شروط الدخول الذكية (التشبع البيعي + تأكيد الاتجاه الصاعد عبر SMA50)
                elif not self.in_position and balance >= self.trade_amount_usdt:
                    # شرط مزدوج قوي: RSI متدني جداً (فرصة شراء) + السعر فوق أو قرب متوسط 50 (اتجاه عام آمن)
                    if rsi < 30.0 and current_price >= (sma_50 * 0.995):
                        logger.info(f"🔥 فرصة استثمارية ذهبية مؤكدة (RSI: {rsi:.2f}). جاري تنفيذ الشراء...")
                        amount_to_buy = self.trade_amount_usdt / current_price
                        await exchange.create_market_buy_order(self.symbol, amount_to_buy)
                        self.entry_price = current_price
                        self.highest_price = current_price  # إعادة ضبط أعلى سعر
                        self.in_position = True
                        logger.info(f"🚀 تم الشراء بنجاح بسعر أساسي: {self.entry_price}")
                    else:
                        logger.info("💤 السوق غير مستقر أو الاتجاه هابط، البوت يحافظ على الكاش بأمان...")
                else:
                    logger.warning("⚠️ الرصيد المتاح غير كافٍ للحد الأدنى للصفقة.")

                await asyncio.sleep(self.poll_interval)

            except ccxt.NetworkError as e:
                logger.warning(f"مشكلة اتصال مؤقتة بالشبكة مع OKX: {e}")
                await asyncio.sleep(20)
            except ccxt.ExchangeError as e:
                logger.warning(f"خطأ من منصة OKX API: {e}")
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"خطأ غير متوقع في محرك التداول: {e}")
                await asyncio.sleep(30)

    async def main(self):
        if not self.api_key or not self.api_secret or not self.passphrase:
            logger.critical("مفاتيح OKX أو كلمة المرور مفقودة في متغيرات البيئة!")
            return

        logger.info("جاري الاتصال بمنصة OKX لتشغيل النسخة المطورة...")
        exchange = ccxt.okx({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'password': self.passphrase,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'
            }
        })

        try:
            await exchange.load_markets()
            logger.info("تم التحقق من الاتصال وبدء العمل بنجاح تام!")
            try:
                await self.run_protected_strategy(exchange)
            finally:
                await exchange.close()
        except ccxt.AuthenticationError as e:
            logger.critical(f"❌ خطأ في المصادقة مع OKX: {e}")
        except Exception as e:
            logger.critical(f"خطأ حرج: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(MaxProtectionTradingBotOKX().main())
    except KeyboardInterrupt:
        logger.info("تم إيقاف النظام يدويًا.")
        
