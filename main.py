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

# قائمة العملات المتعددة
SYMBOLS = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]

ALLOCATION_PCT = 0.80       
STOP_LOSS_PCT = 0.003       
DCA_TRIGGER_PCT = 0.0015    
TRAILING_CALLBACK = 0.001   # تم تعديل نسبة التراجع إلى 0.1% لجني الأرباح بشكل أسرع وأكثر حساسية
TIMEFRAME = "15m"
HIGHER_TIMEFRAME = "1H"

class MultiAssetInstitutionalBot:
    def __init__(self):
        self.positions = {symbol: None for symbol in SYMBOLS}
        self.entry_prices = {symbol: 0.0 for symbol in SYMBOLS}
        self.position_sizes_usdt = {symbol: 0.0 for symbol in SYMBOLS}
        self.position_sizes_asset = {symbol: 0.0 for symbol in SYMBOLS}
        self.highest_prices = {symbol: 0.0 for symbol in SYMBOLS}
        self.dca_used = {symbol: False for symbol in SYMBOLS}
        self.breakeven_activated = {symbol: False for symbol in SYMBOLS}
        self.active_stop_loss_pct = {symbol: STOP_LOSS_PCT for symbol in SYMBOLS}

    def get_signed_headers(self, method, request_path, body=""):
        timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        message = timestamp + method.upper() + request_path + body
        mac = hmac.new(bytes(SECRET_KEY, 'utf-8'), bytes(message, 'utf-8'), hashlib.sha256)
        # السر الأول: استخدام base64 تماماً مثل الكود القديم الناجح
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
            # السر الثاني: المسار النظيف بدون بارامترات تماماً مثل الكود القديم
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

    def get_ticker_price(self, symbol):
        try:
            path = f"/api/v5/market/ticker?instId={symbol}"
            response = requests.get(BASE_URL + path, timeout=10)
            data = response.json()
            if data.get("code") == "0":
                return float(data["data"][0]["last"])
        except Exception as e:
            print(f"[ERROR] Ticker price failed for {symbol}: {e}")
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

    def check_market_conditions(self, symbol):
        try:
            htf_path = f"/api/v5/market/candles?instId={symbol}&bar={HIGHER_TIMEFRAME}&limit=20"
            htf_res = requests.get(BASE_URL + htf_path, timeout=10).json()
            if htf_res.get("code") == "0" and htf_res.get("data"):
                htf_candles_reversed = list(reversed(htf_res["data"]))
                htf_closes = [float(c[4]) for c in htf_candles_reversed]
                htf_ema = sum(htf_closes) / len(htf_closes)
                htf_current = htf_closes[-1]
                if htf_current <= htf_ema:
                    return False

            path = f"/api/v5/market/candles?instId={symbol}&bar={TIMEFRAME}&limit=25"
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

            book_path = f"/api/v5/market/books?instId={symbol}&sz=15"
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
            print(f"[WARNING] Market check error for {symbol}: {e}")
        return False

    def place_order(self, symbol, side, price, amount, is_sz=False):
        try:
            path = "/api/v5/trade/order"
            execution_price = price
            if side == "sell":
                execution_price = price * 0.9990 

            if is_sz:
                size_asset = round(amount, 6)
            else:
                size_asset = round(amount / execution_price, 6)

            if size_asset < 0.000001:
                return None
            
            body = {
                "instId": symbol,
                "tdMode": "cash",
                "side": side,
                "ordType": "limit",
                "px": str(round(execution_price, 2)),
                "sz": str(size_asset)
            }
            
            import json
            body_str = json.dumps(body)
            headers = self.get_signed_headers("POST", path, body_str)
            res = requests.post(BASE_URL + path, headers=headers, data=body_str, timeout=10).json()
            
            if res.get("code") == "0":
                ord_id = res["data"] if isinstance(res["data"], str) else res["data"][0]["ordId"]
                print(f"[SUCCESS] Order {side.upper()} placed on {symbol}, ID: {ord_id}")
                return ord_id
            else:
                print(f"[ERROR] Order rejected on {symbol}: {res.get('msg')}")
        except Exception as e:
            print(f"[ERROR] Place order exception: {e}")
        return None

    def check_order_filled(self, symbol, order_id):
        try:
            path = f"/api/v5/trade/order?instId={symbol}&ordId={order_id}"
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
        print("[OKX-MULTI-ASSET-BOT] النظام متعدد العملات متصل وجاهز بنسبة التراجع الجديدة 0.1%...")
        while True:
            try:
                # 1. متابعة الصفقات المفتوحة
                for symbol in SYMBOLS:
                    if self.positions[symbol] == "LONG":
                        current_price = self.get_ticker_price(symbol)
                        if not current_price:
                            continue

                        if current_price > self.highest_prices[symbol]:
                            self.highest_prices[symbol] = current_price

                        pnl_pct = (current_price - self.entry_prices[symbol]) / self.entry_prices[symbol]
                        drawdown_pct = (self.entry_prices[symbol] - current_price) / self.entry_prices[symbol]

                        print(f"[MONITORING {symbol}] المتوسط: {self.entry_prices[symbol]:.4f} | الحالي: {current_price} | PnL: {pnl_pct*100:.2f}%")

                        if pnl_pct >= 0.005 and not self.breakeven_activated[symbol]:
                            self.breakeven_activated[symbol] = True
                            self.active_stop_loss_pct[symbol] = 0.0000
                            print(f"[BREAKEVEN] تحقيق 0.5% على {symbol}! تم تأمين نقطة الدخول.")

                        if drawdown_pct >= self.active_stop_loss_pct[symbol]:
                            if self.breakeven_activated[symbol]:
                                print(f"[BREAKEVEN EXIT] الخروج بأمان عند نقطة الدخول لـ {symbol}...")
                            else:
                                print(f"[STOP LOSS] تفعيل وقف الخسارة الطارئ لـ {symbol}...")
                            
                            self.place_order(symbol, "sell", current_price, self.position_sizes_asset[symbol], is_sz=True)
                            self.positions[symbol] = None
                            time.sleep(5)
                            continue

                        if drawdown_pct >= DCA_TRIGGER_PCT and not self.dca_used[symbol]:
                            print(f"[DCA] تفعيل التعافي الذكي لـ {symbol}...")
                            dca_budget = self.position_sizes_usdt[symbol]
                            res_id = self.place_order(symbol, "buy", current_price, dca_budget, is_sz=False)
                            if res_id:
                                dca_filled = False
                                for _ in range(6):
                                    time.sleep(5)
                                    if self.check_order_filled(symbol, res_id):
                                        dca_filled = True
                                        break
                                
                                if dca_filled:
                                    dca_asset_qty = dca_budget / current_price
                                    total_cost = self.position_sizes_usdt[symbol] + dca_budget
                                    total_size = self.position_sizes_asset[symbol] + dca_asset_qty
                                    
                                    self.entry_prices[symbol] = total_cost / total_size
                                    self.position_sizes_usdt[symbol] = total_cost
                                    self.position_sizes_asset[symbol] = total_size
                                    self.dca_used[symbol] = True
                                    print(f"[DCA SUCCESS] تم تعزيز {symbol} وتحديث المتوسط: {self.entry_prices[symbol]:.4f}")

                        peak_drawdown = (self.highest_prices[symbol] - current_price) / self.highest_prices[symbol]
                        if pnl_pct >= 0.008 and peak_drawdown >= TRAILING_CALLBACK:
                            print(f"[TAKE PROFIT] جني الأرباح للعملة {symbol} عند القمة: {self.highest_prices[symbol]}")
                            self.place_order(symbol, "sell", current_price, self.position_sizes_asset[symbol], is_sz=True)
                            self.positions[symbol] = None
                            time.sleep(5)

                # 2. البحث عن فرص جديدة بالرصيد الحي المباشر
                avail_balance = self.get_balance()
                active_positions_value = sum(self.position_sizes_usdt.values())
                total_portfolio_value = avail_balance + active_positions_value
                
                print(f"[SCANNER] الكاش المتاح: {avail_balance:.2f} | إجمالي المحفظة الحي: {total_portfolio_value:.2f} USDT")

                for symbol in SYMBOLS:
                    if self.positions[symbol] is None:
                        current_price = self.get_ticker_price(symbol)
                        if not current_price:
                            continue

                        if self.check_market_conditions(symbol):
                            print(f"[FIRE] تطابق الشروط على العملة {symbol}! جاري التنفيذ...")
                            trade_budget = (total_portfolio_value * ALLOCATION_PCT) / 3
                            
                            order_id = self.place_order(symbol, "buy", current_price, trade_budget, is_sz=False)
                            if order_id:
                                print(f"[WAITING FILL] بانتظار تأكيد الشراء لـ {symbol}...")
                                for _ in range(6):
                                    time.sleep(5)
                                    if self.check_order_filled(symbol, order_id):
                                        self.positions[symbol] = "LONG"
                                        self.entry_prices[symbol] = current_price
                                        self.highest_prices[symbol] = current_price
                                        self.position_sizes_usdt[symbol] = trade_budget
                                        self.position_sizes_asset[symbol] = round(trade_budget / current_price, 6)
                                        self.dca_used[symbol] = False
                                        self.breakeven_activated[symbol] = False
                                        self.active_stop_loss_pct[symbol] = STOP_LOSS_PCT
                                        print(f"[ACTIVE SUCCESS] تم فتح الصفقة على {symbol} بسعر: {current_price}")
                                        break
                                else:
                                    print(f"[TIMEOUT] لم يتم تنفيذ الشراء على {symbol}.")
                        else:
                            print(f"[SLEEP] بانتظار الفرصة على {symbol}...")
                    
                    time.sleep(5)

                time.sleep(15)
            except Exception as e:
                print(f"[CRITICAL ERROR] Loop exception: {e}")
                time.sleep(15)

if __name__ == "__main__":
    bot = MultiAssetInstitutionalBot()
    bot.run()
    
