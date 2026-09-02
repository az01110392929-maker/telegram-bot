import os
import asyncio
import logging
from binance import AsyncClient
from binance.exceptions import BinanceAPIException, BinanceRequestException

# إعداد السجلات الهندسية لتوثيق وتتبع كل جزء من رأس المال بدقة فائقة
logging.basicConfig(
    format='%(asctime)s | [MAX-PROTECTION-BOT] | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)
logger = logging.getLogger("MaxProtectionTrader")

class MaxProtectionTradingBot:
    def __init__(self):
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_SECRET_KEY')
        self.symbol = 'BTCUSDT'
        self.trade_amount_usdt = 11.0  # القيمة المتوافقة بدقة مع الحد الأدنى لباينانس
        self.poll_interval = 20  # فترة الفحص المنتظم والمستقر
        
        # حماية صارمة وصارمة جداً لرأس المال لتجنب أي خسارة كبرى
        self.in_position = False
        self.entry_price = 0.0
        self.take_profit_target = 0.015  # ربح مستهدف آمن ومدروس (1.5%)
        self.stop_loss_limit = 0.004     # وقف خسارة حاد وصارم للغاية (0.4%) لحماية الكاش تماماً

    async def get_available_balance(self, client: AsyncClient):
        """فحص رصيد الـ USDT المتاح للتداول الفوري بأمان تام"""
        try:
            account = await client.get_account()
            for asset in account['balances']:
                if asset['asset'] == 'USDT':
                    return float(asset['free'])
            return 0.0
        except Exception as e:
            logger.error(f"خطأ في قراءة الرصيد الفوري: {e}")
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

    async def run_protected_strategy(self, client: AsyncClient):
        logger.info("تم تفعيل النسخة القصوى لحماية الأصول الفورية وإدارة المخاطر بحذر شديد...")

        while True:
            try:
                # 1. جلب السعر الحالي
                ticker = await client.get_symbol_ticker(symbol=self.symbol)
                current_price = float(ticker['price'])

                # 2. فحص الرصيد المتوفر
                balance = await self.get_available_balance(client)

                # 3. جلب الشمعات السعرية لحساب المؤشرات بدقة متناهية
                klines = await client.get_klines(symbol=self.symbol, interval=AsyncClient.KLINE_INTERVAL_1MINUTE, limit=40)
                closes = [float(entry[4]) for entry in klines]
                rsi = self.calculate_rsi(closes)
                
                # حساب المتوسط المتحرك البسيط قصير المدى لفلترة الاتجاه
                sma_20 = sum(closes[-20:]) / 20

                logger.info(f"السعر: {current_price} | المتوسط (SMA20): {sma_20:.2f} | RSI: {rsi:.2f} | الرصيد: {balance:.2f} USDT")

                # 4. إدارة الصفقة المفتوحة وحمايتها لحظياً من أي تراجع
                if self.in_position:
                    price_diff = (current_price - self.entry_price) / self.entry_price
                    logger.info(f"مراقبة صفقة نشطة. نسبة التغير الحالية: {price_diff * 100:.2f}%")

                    # جني الأرباح الآلي
                    if price_diff >= self.take_profit_target:
                        logger.info("🎯 هدف الربح تحقق بنجاح! جاري إرسال أمر بيع فوري لجني الأرباح...")
                        await client.create_order(
                            symbol=self.symbol,
                            side=AsyncClient.SIDE_SELL,
                            type=AsyncClient.ORDER_TYPE_MARKET,
                            quantity=round(self.trade_amount_usdt / current_price, 5)
                        )
                        self.in_position = False
                        logger.info("تم إغلاق الصفقة وتأمين الأرباح بنجاح.")

                    # وقف الخسارة الفوري للحفاظ على رأس المال من أي هبوط
                    elif price_diff <= -self.stop_loss_limit:
                        logger.warning("🛡️ تنبيه حماية رأس المال: تراجع السعر بنسبة وقف الخسارة، جاري التخارج الفوري لحماية المبلغ...")
                        await client.create_order(
                            symbol=self.symbol,
                            side=AsyncClient.SIDE_SELL,
                            type=AsyncClient.ORDER_TYPE_MARKET,
                            quantity=round(self.trade_amount_usdt / current_price, 5)
                        )
                        self.in_position = False
                        logger.warning("تم إغلاق الصفقة لحماية الرصيد الأساسي بالكامل.")

                # 5. شروط الدخول الحذرة والآمنة للغاية (تجنب الخسارة العشوائية)
                elif not self.in_position and balance >= self.trade_amount_usdt:
                    # شرط مزدوج صارم جداً: تشبع بيعي قوي جداً (RSI < 28) + السعر قارب على الاستقرار فوق المتوسط
                    if rsi < 28.0 and current_price >= (sma_20 * 0.997):
                        logger.info(f"🔥 فرصة استثنائية مؤكدة (RSI: {rsi:.2f}). جاري تنفيذ أمر شراء فوري بأعلى معايير الأمان...")
                        order = await client.create_order(
                            symbol=self.symbol,
                            side=AsyncClient.SIDE_BUY,
                            type=AsyncClient.ORDER_TYPE_MARKET,
                            quoteOrderQty=self.trade_amount_usdt
                        )
                        self.entry_price = current_price
                        self.in_position = True
                        logger.info(f"تم تنفيذ الشراء بنجاح عند سعر أساسي: {self.entry_price}")
                    else:
                        logger.info("السوق لا يوفر فرصة آمنة 100% الآن، البوت يفضل الاحتفاظ بالكاش وعدم المخاطرة...")
                else:
                    logger.warning("الرصيد المتاح لا يغطي الحد الأدنى للصفقة الآمنة حالياً.")

                await asyncio.sleep(self.poll_interval)

            except BinanceAPIException as e:
                logger.warning(f"خطأ مؤقت من منصة باينانس API: {e.message}")
                await asyncio.sleep(30)
            except BinanceRequestException as e:
                logger.warning(f"مشكلة اتصال مؤقتة بالشبكة: {e}")
                await asyncio.sleep(20)
            except Exception as e:
                logger.error(f"خطأ غير متوقع في محرك التداول الآمن: {e}")
                await asyncio.sleep(30)

    async def main(self):
        if not self.api_key or not self.api_secret:
            logger.critical("مفاتيح باينانس مفقودة تماماً في متغيرات البيئة!")
            return

        client = await AsyncClient.create(self.api_key, self.api_secret)
        try:
            await self.run_protected_strategy(client)
        finally:
            await client.close_connection()

if __name__ == "__main__":
    try:
        asyncio.run(MaxProtectionTradingBot().main())
    except KeyboardInterrupt:
        logger.info("تم إيقاف النظام الهندسي الآمن يدويًا.")
        
