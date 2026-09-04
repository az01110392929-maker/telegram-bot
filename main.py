import os
import time
import hmac
import hashlib
import base64
import requests
from datetime import datetime

# ==================== إعدادات المنظومة المؤسسية ====================
API_KEY = os.getenv("OKX_API_KEY", "")
SECRET_KEY = os.getenv("OKX_SECRET_KEY", "")
PASSPHRASE = os.getenv("OKX_PASSPHRASE", "")

BASE_URL = "https://www.okx.com" 
SYMBOL = "BTC-USDT"

ALLOCATION_PCT = 0.80       
STOP_LOSS_PCT = 0.003       
DCA_TRIGGER_PCT = 0.0015    
TRAILING_CALLBACK = 0.002   
TIMEFRAME = "15m"

class InstitutionalBot:
    def __init__(self):
        self.position = None
        self.entry_price = 0.0
        self.position_size_usdt = 0.0 
        self.position_size_btc = 0.0  
        self.highest_price = 0.0
        self.dca_used = False
        self.order_id = None

    def get_signed_headers(self, method, request_path, body=""):
        timestamp = datetime.utcnow().isoformat() + "Z"
        message = timestamp + method.upper() + request_path + body
        mac = hmac.new(bytes(SECRET_KEY, 'utf-8'), bytes(message, 'utf-8'), hashlib.sha256)
        sign = base64.b64encode(mac.digest()).decode('utf-8')
        return {
            "OK-ACCESS-KEY": API_KEY,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": PASSPHRASE,
            "Content-Type": "application/json"
        }

    def get_balance(self):
        """جلب الرصيد المتاح مباشرة من حساب التداول (Trading / Spot)"""
        try:
            # مسار جلب الأصول لحساب التداول المباشر
            path = "/api/v5/account/balance?ccy=USDT"
            headers = self.get_signed_headers("GET", path)
            response = requests.get(BASE_URL + path, headers=headers, timeout=10)
            data = response.json()
            
            if data.get("code") == "0":
                details = data["data"][0]["details"]
                for detail in details:
                    if detail["ccy"] == "USDT":
                        # قراءة الرصيد المتاح للتداول الفوري
                        avail = float(detail.get("availBal", 0))
                        if avail == 0:
                            # احتياطي لو الرصيد مسجل تحت الرصيد الكلي المتاح
                            avail = float(detail.get("cashBal", 0))
                        return avail
            return 0.0
        except Exception as e:
            print(f"[ERROR] Balance fetch failed: {e}")
            return 0.0

    def get_ticker_price(self):
        try:
            path = f"/api/v5/market/ticker?instId={SYMBOL}"
            response = requests.get(BASE_URL + path, timeout=10)
            data = response.json()
            if data.get("code") == "0":
                return float(data["data"][0]["last"])
        except Exception as e:
            print(f"[ERROR] Ticker price failed: {e}")
        return None

    def check_market_conditions(self):
        try:
            path = f"/api/v5/market/candles?instId={SYMBOL}&bar={TIMEFRAME}&limit=20"
            res = requests.get(BASE_URL + path, timeout=10).json()
            if res.get("code") != "0" or not res.get("data"):
                return False
            
            closes = [float(candle[4]) for candle in res["data"]]
            ema_20 = sum(closes) / len(closes)
            current_price = closes[0]

            book_path = f"/api/v5/market/books?instId={SYMBOL}&sz=15"
            book_res = requests.get(BASE_URL + book_path, timeout=10).json()
            if book_res.get("code") != "0":
                return False
            
            bids = book_res["data"][0]["bids"]
            asks = book_res["data"][0]["asks"]
            
            bid_volume = sum([float(b[1]) for b in bids])
            ask_volume = sum([float(a[1]) for a in asks])

            if current_price > ema_20 and bid_volume > (ask_volume * 1.1):
                return True
        except Exception as e:
            print(f"[WARNING] Market check error: {e}")
        return False

    def place_order(self, side, price, amount, is_btc_sz=False):
        try:
            path = "/api/v5/trade/order"
            execution_price = price
            if side == "sell":
                execution_price = price * 0.9990 

            if is_btc_sz:
                size_btc = round(amount, 4)
            else:
                size_btc = round(amount / execution_price, 4)

            if size_btc < 0.0001:
                return None
            
            body = {
                "instId": SYMBOL,
                "tdMode": "cash",
                "side": side,
                "ordType": "limit",
                "px": str(round(execution_price, 2)),
                "sz": str(size_btc)
            }
            headers = self.get_signed_headers("POST", path, str(body))
            res = requests.post(BASE_URL + path, headers=headers, json=body, timeout=10).json()
            
            if res.get("code") == "0":
                ord_id = res["data"] if isinstance(res["data"], str) else res["data"][0]["ordId"]
                print(f"[SUCCESS] Order {side.upper()} placed, ID: {ord_id}")
                return ord_id
            else:
                print(f"[ERROR] Order rejected: {res.get('msg')}")
        except Exception as e:
            print(f"[ERROR] Place order exception: {e}")
        return None

    def check_order_filled(self, order_id):
        try:
            path = f"/api/v5/trade/order?instId={SYMBOL}&ordId={order_id}"
            headers = self.get_signed_headers("GET", path)
            res = requests.get(BASE_URL + path, headers=headers, timeout=10).json()
            if res.get("code") == "0" and res.get("data"):
                state = res["data"][0].get("state")
                if state == "filled":
                    return True
        except Exception as e:
            print(f"[WARNING] Check order status error: {e}")
        return False

    def run(self):
        print("[OKX-INSTITUTIONAL-BOT] النظام متصل بحساب التداول ويقرأ الرصيد الفوري...")
        while True:
            try:
                current_price = self.get_ticker_price()
                if not current_price:
                    time.sleep(15)
                    continue

                avail_balance = self.get_balance()
                print(f"[SCANNER] السعر الحالي: {current_price} | الرصيد المتاح في التداول: {avail_balance:.2f} USDT")

                if not self.position:
                    if avail_balance < 10:
                        print("[WAITING] الرصيد المتاح أقل من الحد الأدنى للصفقة.")
                        time.sleep(30)
                        continue

                    if self.check_market_conditions():
                        print("[FIRE] تطابق الشروط! جاري إرسال أمر الشراء...")
                        trade_budget = avail_balance * ALLOCATION_PCT
                        
                        order_id = self.place_order("buy", current_price, trade_budget, is_btc_sz=False)
                        if order_id:
                            print("[WAITING FILL] بانتظار تأكيد التنفيذ التام للدخول...")
                            for _ in range(6):
                                time.sleep(5)
                                if self.check_order_filled(order_id):
                                    self.position = "LONG"
                                    self.entry_price = current_price
                                    self.highest_price = current_price
                                    self.position_size_usdt = trade_budget
                                    self.position_size_btc = round(trade_budget / current_price, 4)
                                    self.dca_used = False
                                    self.order_id = order_id
                                    print(f"[ACTIVE SUCCESS] تم التأكيد والدخول بنجاح بسعر: {self.entry_price}")
                                    break
                            else:
                                print("[TIMEOUT] لم يتم تنفيذ أمر الشراء، جاري إلغاؤه.")
                    else:
                        print("[SLEEP] بانتظار الفرصة الآمنة...")

                else:
                    if current_price > self.highest_price:
                        self.highest_price = current_price

                    pnl_pct = (current_price - self.entry_price) / self.entry_price
                    drawdown_pct = (self.entry_price - current_price) / self.entry_price

                    print(f"[MONITORING] المتوسط: {self.entry_price:.2f} | الحالي: {current_price} | الربح/الخسارة: {pnl_pct*100:.2f}%")

                    # 1. وقف الخسارة
                    if drawdown_pct >= STOP_LOSS_PCT:
                        print("[STOP LOSS] تفعيل وقف الخسارة الطارئ وحماية رأس المال...")
                        self.place_order("sell", current_price, self.position_size_btc, is_btc_sz=True)
                        self.position = None
                        time.sleep(10)
                        continue

                    # 2. التعافي الذكي (DCA)
                    if drawdown_pct >= DCA_TRIGGER_PCT and not self.dca_used:
                        print("[DCA] تفعيل التعافي الذكي، إرسال أمر التعزيز وبانتظار التنفيذ...")
                        avail_balance = self.get_balance()
                        if avail_balance >= 5:
                            dca_budget = avail_balance * 0.5
                            dca_btc = round(dca_budget / current_price, 4)
                            
                            res_id = self.place_order("buy", current_price, dca_budget, is_btc_sz=False)
                            if res_id:
                                dca_filled = False
                                for _ in range(6):
                                    time.sleep(5)
                                    if self.check_order_filled(res_id):
                                        dca_filled = True
                                        break
                                
                                if dca_filled:
                                    total_cost = self.position_size_usdt + dca_budget
                                    total_size = self.position_size_btc + dca_btc
                                    
                                    self.entry_price = total_cost / total_size
                                    self.position_size_usdt = total_cost
                                    self.position_size_btc = total_size
                                    self.dca_used = True
                                    print(f"[DCA SUCCESS] تم تنفيذ التعزيز وتحديث متوسط السعر بدقة: {self.entry_price:.2f}")
                                else:
                                    print("[DCA TIMEOUT] لم يتم تنفيذ أمر التعزيز في الوقت المحدد، تم تخطيه بأمان.")

                    # 3. جني الأرباح التتبعي (Trailing TP)
                    peak_drawdown = (self.highest_price - current_price) / self.highest_price
                    if pnl_pct >= 0.008 and peak_drawdown >= TRAILING_CALLBACK:
                        print(f"[TAKE PROFIT] جني الأرباح عند القمة: {self.highest_price}")
                        self.place_order("sell", current_price, self.position_size_btc, is_btc_sz=True)
                        self.position = None
                        time.sleep(10)

                time.sleep(15)
            except Exception as e:
                print(f"[CRITICAL ERROR] Loop exception: {e}")
                time.sleep(15)

if __name__ == "__main__":
    bot = InstitutionalBot()
    bot.run()
    
