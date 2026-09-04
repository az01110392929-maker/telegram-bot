import os
import time
import hmac
import hashlib
import base64
import requests
from datetime import datetime, timezone

# ==================== إعدادات البيئة الآمنة ====================
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
HIGHER_TIMEFRAME = "1H"

class InstitutionalBot:
    def __init__(self):
        self.position = None
        self.entry_price = 0.0
        self.position_size_usdt = 0.0 
        self.position_size_btc = 0.0  
        self.highest_price = 0.0
        self.dca_used = False
        self.order_id = None
        self.breakeven_activated = False
        self.active_stop_loss_pct = STOP_LOSS_PCT

    def get_signed_headers(self, method, request_path, body=""):
        timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
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
        try:
            path = "/api/v5/account/balance"
            headers = self.get_signed_headers("GET", path)
            response = requests.get(BASE_URL + path, headers=headers, timeout=10)
            data = response.json()
            
            if data.get("code") == "0" and data.get("data"):
                details = data["data"][0].get("details", [])
                for detail in details:
                    if detail.get("ccy") == "USDT":
                        avail = float(detail.get("availBal", 0))
                        cash = float(detail.get("cashBal", 0))
                        total_avail = avail if avail > 0 else cash
                        if total_avail > 0:
                            return total_avail
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

    def calculate_adx(self, candles, period=14):
        try:
            if len(candles) < period + 1:
                return 25.0
            
            tr_list = []
            plus_dm_list = []
            minus_dm_list = []
            
            for i in range(1, len(candles)):
                high = float(candles[i][2])
                low = float(candles[i][3])
                prev_high = float(candles[i-1][2])
                prev_low = float(candles[i-1][3])
                prev_close = float(candles[i-1][4])
                
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_list.append(tr)
                
                plus_dm = high - prev_high if (high - prev_high) > (prev_low - low) and (high - prev_high) > 0 else 0
                minus_dm = prev_low - low if (prev_low - low) > (high - prev_high) and (prev_low - low) > 0 else 0
                
                plus_dm_list.append(plus_dm)
                minus_dm_list.append(minus_dm)
                
            avg_tr = sum(tr_list[-period:]) / period
            if avg_tr == 0:
                return 0.0
            avg_plus_di = (sum(plus_dm_list[-period:]) / period) / avg_tr * 100
            avg_minus_di = (sum(minus_dm_list[-period:]) / period) / avg_tr * 100
            
            sum_di = avg_plus_di + avg_minus_di
            if sum_di == 0:
                dx = 0
            else:
                dx = abs(avg_plus_di - avg_minus_di) / sum_di * 100
            return dx
        except Exception:
            return 25.0

    def check_market_conditions(self):
        try:
            # 1. فحص الاتجاه الأكبر (فريم الساعة)
            htf_path = f"/api/v5/market/candles?instId={SYMBOL}&bar={HIGHER_TIMEFRAME}&limit=20"
            htf_res = requests.get(BASE_URL + htf_path, timeout=10).json()
            if htf_res.get("code") == "0" and htf_res.get("data"):
                htf_candles_reversed = list(reversed(htf_res["data"]))
                htf_closes = [float(c[4]) for c in htf_candles_reversed]
                htf_ema = sum(htf_closes) / len(htf_closes)
                htf_current = htf_closes[-1]
                if htf_current <= htf_ema:
                    return False

            # 2. فحص الفريم الأساسي (15 دقيقة) وعكس الشموع لترتيب صحيح للـ ADX
            path = f"/api/v5/market/candles?instId={SYMBOL}&bar={TIMEFRAME}&limit=25"
            res = requests.get(BASE_URL + path, timeout=10).json()
            if res.get("code") != "0" or not res.get("data"):
                return False
            
            candles_reversed = list(reversed(res["data"]))
            closes = [float(candle[4]) for candle in candles_reversed]
            ema_20 = sum(closes[-20:]) / 20
            current_price = closes[-1]

            adx_val = self.calculate_adx(candles_reversed)
            if adx_val < 20:
                return False

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
                size_btc = round(amount, 6)
            else:
                size_btc = round(amount / execution_price, 6)

            if size_btc < 0.000001:
                return None
            
            body = {
                "instId": SYMBOL,
                "tdMode": "cash",
                "side": side,
                "ordType": "limit",
                "px": str(round(execution_price, 2)),
                "sz": str(size_btc)
            }
            
            import json
            body_str = json.dumps(body)
            headers = self.get_signed_headers("POST", path, body_str)
            res = requests.post(BASE_URL + path, headers=headers, data=body_str, timeout=10).json()
            
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
        print("[OKX-INSTITUTIONAL-BOT] النظام متصل وجاهز بالتحديثات النهائية والمصححة...")
        while True:
            try:
                current_price = self.get_ticker_price()
                if not current_price:
                    time.sleep(15)
                    continue

                avail_balance = self.get_balance()
                print(f"[SCANNER] السعر الحالي: {current_price} | الرصيد المتاح في الحساب: {avail_balance:.2f} USDT")

                if not self.position:
                    if avail_balance < 10:
                        print("[WAITING] الرصيد المتاح أقل من الحد الأدنى للصفقة.")
                        time.sleep(30)
                        continue

                    if self.check_market_conditions():
                        print("[FIRE] تطابق الشروط بنجاح! جاري إرسال أمر الشراء...")
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
                                    self.position_size_btc = round(trade_budget / current_price, 6)
                                    self.dca_used = False
                                    self.order_id = order_id
                                    self.breakeven_activated = False
                                    self.active_stop_loss_pct = STOP_LOSS_PCT
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

                    # تفعيل تأمين نقطة الدخول عند تحقيق 0.5% ربح
                    if pnl_pct >= 0.005 and not self.breakeven_activated:
                        self.breakeven_activated = True
                        self.active_stop_loss_pct = 0.0000
                        print("[BREAKEVEN] تم تحقيق ربح 0.5%! جاري تأمين نقطة الدخول (رفع وقف الخسارة لسعر الدخول)...")

                    if drawdown_pct >= self.active_stop_loss_pct:
                        if self.breakeven_activated:
                            print("[BREAKEVEN EXIT] الخروج عند نقطة الدخول بأمان تام...")
                        else:
                            print("[STOP LOSS] تفعيل وقف الخسارة الطارئ وحماية رأس المال...")
                        self.place_order("sell", current_price, self.position_size_btc, is_btc_sz=True)
                        self.position = None
                        time.sleep(10)
                        continue

                    if drawdown_pct >= DCA_TRIGGER_PCT and not self.dca_used:
                        print("[DCA] تفعيل التعافي الذكي، إرسال أمر التعزيز بالرصيد المتاح وبانتظار التنفيذ...")
                        avail_balance = self.get_balance()
                        if avail_balance >= 5:
                            dca_budget = avail_balance
                            dca_btc = round(dca_budget / current_price, 6)
                            
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
    
