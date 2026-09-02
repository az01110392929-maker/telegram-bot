import os
import asyncio
import logging
from binance import AsyncClient
from binance.exceptions import BinanceAPIException, BinanceRequestException

# إعداد السجلات الهندسية المتطورة
logging.basicConfig(
    format='%(asctime)s | [ASYNC-ENGINE] | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)
logger = logging.getLogger("BinanceMastermindBot")

class GeniusBinanceEngine:
    def __init__(self):
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_SECRET_KEY')
        # قائمة العملات القابلة للتوسيع الفوري
        self.symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT']
        self.poll_interval = 6  # سرعة فائقة في المراقبة بلا استنزاف للموارد

    async def monitor_symbol(self, client: AsyncClient, symbol: str):
        """حلقة مراقبة غير متزامنة فائقة السرعة لكل زوج عملات"""
        backoff = 2
        logger.info(تم تفعيل العقد الذكي لمراقبة الزوج: {symbol})

        while True:
            try:
                ticker = await client.get_symbol_ticker(symbol=symbol)
                price = ticker['price']
                logger.info(الزوج [{symbol}] -> السعر اللحظي: {price} USDT)
                backoff = 2  # إعادة ضبط عند النجاح التام
                await asyncio.sleep(self.poll_interval)

            except BinanceAPIException as e:
                logger.warning(خطأ باينانس API للزوج {symbol}: [رمز {e.status_code}] {e.message})
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
            except BinanceRequestException as e:
                logger.warning(مشكلة شبكة مؤقتة للزوج {symbol}: {e})
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(استثناء غير متوقع في مسار {symbol}: {e})
                await asyncio.sleep(10)

    async def main(self):
        """المحرك العبقري المدبر لكافة العمليات والروابط بالتوازي المطلق"""
        if not self.api_key or not self.api_secret:
            logger.critical(خطأ حرج: مفاتيح باينانس مفقودة تماماً في متغيرات البيئة لـ Railway.)
            return

        logger.info(بدء تشغيل المحرك العبقري غير المتزامن لباينانس...)

        while True:
            client = None
            try:
                # إنشاء اتصال عالي الأداء غير متزامن
                client = await AsyncClient.create(self.api_key, self.api_secret)
                logger.info(تم الاتصال بنجاح وتفعيل عميل باينانس غير المتزامن (AsyncClient).)

                # تشغيل مهام مراقبة جميع العملات دفعة واحدة وفي نفس اللحظة
                tasks = [self.monitor_symbol(client, symbol) for symbol in self.symbols]
                await asyncio.gather(*tasks)

            except Exception as e:
                logger.error(انهيار مؤقت في حلقة الاتصال الرئيسية: {e}. جارٍ إعادة الهيكلة والاتصال...)
                await asyncio.sleep(10)
            finally:
                if client:
                    await client.close_connection()
                    logger.info(إغلاق الجلسة السابقة بأمان تام استعداداً لإعادة الاتصال.)

if __name__ == __main__":
    try:
        asyncio.run(GeniusBinanceEngine().main())
    except KeyboardInterrupt:
        logger.info(تم إيقاف النظام يدويًا.)
      
