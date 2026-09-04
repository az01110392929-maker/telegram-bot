import os
import asyncio
import logging
import ccxt.async_support as ccxt

# إعداد السجلات الهندسية المتقدمة لتوثيق وتتبع كل جزء من رأس المال بدقة فائقة
logging.basicConfig(
    format='%(asctime)s | [OKX-INSTITUTIONAL-BOT] | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)
logger = logging.getLogger("InstitutionalTraderOKX")

class InstitutionalTradingBotOKX:
    def __init__(self):
        # سحب المتغيرات البيئية من Railway وتطهيرها من أي مسافات فارغة لتجنب أخطاء الترميز
        self.api_key = os.getenv('OKX_API_KEY', '').strip()
        self.api_secret = os.getenv('OKX_SECRET_KEY', '').strip()
        self.passphrase = os.getenv('OKX_PASSPHRASE', '').strip()
        
        # بحث احتياطي تلقائي إذا كانت المتغيرات مسجلة بأسماء مختصرة
        if not self.api_key or not self.api_secret or not self.passphrase:
            for k, v in os.environ.items():
                k_upper = k.upper()
                if 'API' in k_upper and not self.api_key:
                    self.api_key = v.strip()
                elif ('SEC' in k_upper) and not self.api_secret:
                    self.api_secret = v.strip()
                elif ('PAS' in k_upper) and not self.passphrase:
                    self.passphrase = v.strip()

        self.symbol = 'BTC/USDT'
        self.poll_interval = 20  # فترة الفحص المنتظم
        
        # إعدادات هندسية متقدمة لإدارة رأس المال والمخاطر
        self.base_max_allocation_pct = 0.80  # استخدام 80% من الرصيد المتاح للرغبة في صفقات كبرى (تقريب 50$ من رصيدك)
        self.trailing_drop_pct = 0.002       # نسبة ارتداد تتبع الأرباح (0.2%)
        self.dca_threshold_pct = 0.0015      # نسبة تفعيل التعافي الذكي (0.15%)
        
        # حالة الصفقة الحالية والمتابعة
        self.in_position = False
        self.entry_price = 0.0
        self.total_amount = 0.0
        self.total_cost = 0.0
        self.dca_used = False
        self.highest_price = 0.0
        self.trailing_active = False
        self.current_tp_target = 0.012
        self.current_sl_target = 0.003

    async def get_available_balance(self, exchange: ccxt.okx):
        """فحص رصيد الـ USDT المتاح للتداول الفوري (Spot) بأمان تام"""
        try:
            balance = await exchange.fetch_balance()
            free_usdt = balance['free'].get('USDT', 0.0) if 'free' in balance else 0.0
            return float(free_usdt)
        except Exception as e:
            logger.error(f"خطأ في قراءة الرصيد الفوري من OKX: {e}")
            return 0.0

    async def institutional_market_analysis(self, exchange: ccxt.okx):
        """
        تحليل مؤسسي متكامل: تصفية جدران التلاعب (Spoofing)، 
        توافق الأطر الزمنية، ومؤشر ATR الديناميكي لتحديد الأهداف
        """
        try:
            # 1. فحص دفتر الأوامر (Order Book) لكشف جدران التلاعب والسيولة الحقيقية
            order_book = await exchange.fetch_order_book(self.symbol, limit=50)
            bids = order_book['bids']
            asks = order_book['asks']
            
            bids_top_vol = sum([b[1] for b in bids[:15]])
            asks_top_vol = sum([a[1] for a in asks[:15]])
            
            if asks_top_vol > 0 and (bids_top_vol / asks_top_vol) < 1.2:
                return False, 0, 0, 0

            # 2. فحص الترند على إطار الساعة (1h)
            ohlcv_1h = await exchange.fetch_ohlcv(self.symbol, timeframe='1h', limit=30)
            closes_1h = [c[4] for c in ohlcv_1h]
            ema_1h = sum(closes_1h) / len(closes_1h)
            if closes_1h[-1] < ema_1h:
                return False, 0, 0, 0

            # 3. فحص إطار الـ 15 دقيقة ومؤشر التقلب ATR
            ohlcv_15m = await exchange.fetch_ohlcv(self.symbol, timeframe='15m', limit=50)
            if not ohlcv_15m or len(ohlcv_15m) < 50:
                return False, 0, 0, 0

            closes_15m = [c[4] for c in ohlcv_15m]
            ema_15m = sum(closes_15m) / len(closes_15m)
            current_price = closes_15m[-1]

            if current_price < ema_15m:
                return False, 0, 0, 0

            highs = [c[2] for c in ohlcv_15m[-14:]]
            lows = [c[3] for c in ohlcv_15m[-14:]]
            tr_list = [highs[i] - lows[i] for i in range(len(highs))]
            avg_atr = sum(tr_list) / len(tr_list)
            
            volatility_ratio = avg_atr / current_price
            if volatility_ratio < 0.0005:
                return False, 0, 0, 0

            dynamic_tp = max(0.008, min(0.015, volatility_ratio * 1.5))
            dynamic_sl = 0.0025
            strength_score = min(1.0, (bids_top_vol / (asks_top_vol + 1e-8)) / 2.0)

            return True, dynamic_tp, dynamic_sl, strength_score

        except Exception as e:
            logger.error(f"خطأ في التحليل المؤسسي: {e}")
            return False, 0, 0, 0

    async def run_protected_strategy(self, exchange: ccxt.okx):
        logger.info("تم تفعيل محرك التداول المؤسسي المتقدم مع حماية رأس المال وربط السيولة الكاملة...")

        while True:
            try:
                # 1. جلب السعر الحالي والرصيد المتاح
                ticker = await exchange.fetch_ticker(self.symbol)
                current_price = float(ticker['last'])
                balance = await self.get_available_balance(exchange)

                logger.info(f"📊 [OKX-Scanner] السعر الحالي: {current_price} | الرصيد الحر المتاح: {balance:.2f} USDT")

                # 2. إدارة الصفقة المفتوحة والحماية لحظياً (مع تتبع الأرباح والتعافي الذكي DCA)
                if self.in_position:
                    tp_price = self.entry_price * (1 + self.current_tp_target)
                    sl_price = self.entry_price * (1 - self.current_sl_target)
                    price_diff = (current_price - self.entry_price) / self.entry_price
                    logger.info(f"مراقبة صفقة نشطة. متوسط الدخول: {self.entry_price:.2f} | التغير: {price_diff * 100:.2f}%")

                    # نظام التعافي الذكي (Smart DCA) عند حدوث هبوط تكتيكي مؤقت
                    if not self.dca_used and current_price <= (self.entry_price * (1 - self.dca_threshold_pct)):
                        logger.info("🔄 تفعيل التعافي الذكي (DCA) لتعديل متوسط السعر وتقليل المخاطر...")
                        dca_budget = min(balance * 0.4, 30.0)
                        if dca_budget >= 10.0:
                            amount_to_buy = dca_budget / current_price
                            order = await exchange.create_market_buy_order(self.symbol, amount_to_buy)
                            filled_price = float(order.get('average', current_price) or current_price)
                            filled_amount = float(order.get('filled', amount_to_buy))
                            
                            self.total_cost += (filled_price * filled_amount)
                            self.total_amount += filled_amount
                            self.entry_price = self.total_cost / self.total_amount
                            self.dca_used = True
                            logger.info(f"تم تنفيذ تعزيز DCA بنجاح. متوسط السعر الجديد: {self.entry_price:.2f}")

                    # وقف الخسارة الفوري المحمي
                    if current_price <= sl_price:
                        logger.warning("🛡️ تفعيل وقف الخسارة لحماية رأس المال الأساسي. جاري الخروج الفوري...")
                        await exchange.create_market_sell_order(self.symbol, self.total_amount)
                        self.in_position = False
                        logger.warning("تم إغلاق الصفقة بالكامل لحماية الرصيد.")
                        continue

                    # تحديث القمة السعرية لتتبع الأرباح (Trailing Take Profit)
                    if current_price > self.highest_price:
                        self.highest_price = current_price

                    if not self.trailing_active and current_price >= tp_price:
                        self.trailing_active = True
                        logger.info(f"🎯 بلوغ الهدف! تفعيل نظام ملاحقة الأرباح العليا من قمة: {self.highest_price}")

                    if self.trailing_active:
                        drop_threshold = self.highest_price * (1 - self.trailing_drop_pct)
                        if current_price <= drop_threshold:
                            logger.info("📈 ارتداد السعر من القمة -> جني الأرباح القصوى وإغلاق الصفقة!")
                            await exchange.create_market_sell_order(self.symbol, self.total_amount)
                            self.in_position = False
                            logger.info("تم جني الأرباح وتأمين الكاش بنجاح.")
                            continue

                # 3. شروط البحث والدخول في صفقات جديدة بناءً على السيولة المؤسسية
                elif not self.in_position:
                    is_valid, dyn_tp, dyn_sl, strength_score = await self.institutional_market_analysis(exchange)
                    
                    if is_valid:
                        # تخصيص نسبة ذكية من إجمالي الرصيد المتاح (80% مضروبة في قوة السيولة)
                        allocated_budget = balance * self.base_max_allocation_pct * strength_score
                        
                        if allocated_budget >= 10.0:
                            logger.info(f"🔥 تطابق الشروط المؤسسية! جاري تنفيذ أمر شراء بقيمة: {allocated_budget:.2f}$")
                            amount_to_buy = allocated_budget / current_price
                            
                            order = await exchange.create_market_buy_order(self.symbol, amount_to_buy)
                            filled_price = float(order.get('average', current_price) or current_price)
                            filled_amount = float(order.get('filled', amount_to_buy))
                            
                            # تسجيل تفاصيل الصفقة النشطة
                            self.entry_price = filled_price
                            self.total_amount = filled_amount
                            self.total_cost = filled_price * filled_amount
                            self.current_tp_target = dyn_tp
                            self.current_sl_target = dyn_sl
                            self.dca_used = False
                            self.highest_price = filled_price
                            self.trailing_active = False
                            self.in_position = True
                            
                            logger.info(f"تم تنفيذ الدخول المؤسسي بنجاح عند سعر: {self.entry_price}")
                        else:
                            logger.warning("⚠️ الرصيد المتاح لا يغطي الحد الأدنى للصفقة المؤسسية (10$).")
                    else:
                        logger.info("💤 شروط السيولة لا تلبي المعايير المؤسسية حالياً، البوت ينتظر الفرصة المثلى...")

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

        logger.info("جاري تهيئة الاتصال الآمن بمنصة OKX (تداول فوري Spot)...")
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
            logger.info("تم التحقق من مفاتيح OKX والاتصال بنجاح تام!")
            try:
                await self.run_protected_strategy(exchange)
            finally:
                await exchange.close()
        except ccxt.AuthenticationError as e:
            logger.critical(f"❌ رفضت OKX المفاتيح أو كلمة المرور: {e}")
        except Exception as e:
            logger.critical(f"خطأ حرج في تهيئة العميل مع OKX: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(InstitutionalTradingBotOKX().main())
    except KeyboardInterrupt:
        logger.info("تم إيقاف النظام الهندسي الآمن يدويًا.")
        
