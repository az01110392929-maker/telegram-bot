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

SYMBOLS = ["SUI-USDT", "DOGE-USDT", "SOL-USDT"]

ALLOCATION_PCT = 0.80       
MAX_SINGLE_ASSET_PCT = 0.33 
STOP_LOSS_PCT = 0.003       
DCA_TRIGGER_PCT = 0.002     
TAKE_PROFIT_PCT = 0.008     
TIMEFRAME = "15m"
HIGHER_TIMEFRAME = "1H"
CHECK_INTERVAL = 7          

class UltimateInstitutionalBot:
    def __init__(self):
        self.positions = {symbol: None for symbol in SYMBOLS}
        self.entry_prices = {symbol: 0.0 for symbol in SYMBOLS}
        self.position_sizes_usdt = {symbol: 0.0 for symbol in SYMBOLS}
        self.position_sizes_asset = {symbol: 0.0 for symbol in SYMBOLS}
        self.dca_used = {symbol: False for symbol in SYMBOLS}
        self.breakeven_activated = {symbol: False for symbol in SYMBOLS}
        self.active_stop_loss_pct = {symbol: STOP_LOSS_PCT for symbol in SYMBOLS}

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

    def get_instrument_limits(self, symbol):
        """جلب الحد الأدنى لحجم العقود ودقة الأرقام لكل عملة من OKX لتجنب الرفض"""
        try:
            path = f"/api/v5/public/instruments?instType=SPOT&instId={symbol}"
            res = requests.get(BASE_URL + path, timeout=10).json()
            if res.get("code") == "0" and res.get("data"):
                item = res["data"][0]
                return float(item.get("lotSz", 1)), float(item.get("minSz", 1))
        except Exception:
            pass
        return 1.0, 1.0

    def calculate_adx(self, candles, period=14):
        try:
            if len(candles) < period + 1:
                return 25.0
            
            tr_list, plus_dm_list, minus_dm_list = [], [], []
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
        """خوارزمية فحص النخبة للفرص الذهبية الحقيقية"""
        try:
            htf_path = f"/api/v5/market/candles?instId={symbol}&bar={HIGHER_TIMEFRAME}&limit=20"
            htf_res = requests.get(BASE_URL + htf_path, timeout=10).json()
            if htf_res.get("code") == "0" and htf_res.get("data"):
                htf_closes = [float(c[4]) for c in reversed(htf_res["data"])]
                if htf_closes[-1] <= (sum(htf_closes) / len(htf_closes)):
                    return False

            path = f"/api/v5/market/candles?instId={symbol}&bar={TIMEFRAME}&limit=25"
            res = requests.get(BASE_URL + path, timeout=10).json()
            if res.get("code") != "0" or not res.get("data"):
                return False
            
            candles_rev = list(reversed(res["data"]))
            closes = [float(c[4]) for c in candles_rev]
            ema_20 = sum(closes[-20:]) / 20
            
            if closes[-1] <= ema_20:
                return False
            if self.calculate_adx(candles_rev) < 22:
                return False

            book_res = requests.get(BASE_URL + f"/api/v5/market/books?instId={symbol}&sz=15", timeout=10).json()
            if book_res.get("code") != "0":
                return False
            
            bids_vol = sum([float(b[1]) for b in book_res["data"][0]["bids"]])
            asks_vol = sum([float(a[1]) for a in book_res["data"][0]["asks"]])

            return bids_vol > (asks_vol * 1.15)
        except Exception:
            return False

    def place_order(self, symbol, side, price, amount, is_sz=False):
        try:
            path = "/api/v5/trade/order"
            execution_price = price
            if side == "sell":
                execution_price = price * 0.9985 # سعر تفضيلي لتنفيذ البيع الفوري السريع

            lot_sz, min_sz = self.get_instrument_limits(symbol)

            if is_sz:
                raw_size = amount
            else:
                raw_size = amount / execution_price

            # ضبط الحجم ليوافق بدقة قوانين منصة OKX للعملات المختلفة
            multiplier = round(raw_size / lot_sz)
            size_asset = multiplier * lot_sz
            if size_asset < min_sz:
                size_asset = min_sz

            # تنسيق عدد الخانات العشرية بناءً على حجم العملة
            precision = 2 if symbol.startswith("SOL") else (0 if symbol.startswith("DOGE") else 4)
            size_str = f"{size_asset:.{precision}f}"

            body = {
                "instId": symbol,
                "tdMode": "cash",
                "side": side,
                "ordType": "market" if side == "sell" else "limit", # استخدام Market للبيع الفوري المضمون
                "px": str(round(execution_price, 2)) if side == "buy" else "",
                "sz": size_str
            }
            if side == "sell":
                body.pop("px") # أوامر الماركت لا تحتاج لسعر محدد عند البيع الفوري

            import json
            body_str = json.dumps(body)
            headers = self.get_signed_headers("POST", path, body_str)
            res = requests.post(BASE_URL + path, headers=headers, data=body_str, timeout=10).json()
            
            if res.get("code") == "0":
                ord_id = res["data"] if isinstance(res["data"], str) else res["data"][0]["ordId"]
                print(f"[ULTRA SUCCESS] Order {side.upper()} executed on {symbol}, ID: {ord_id}")
                return ord_id
            else:
                print(f"[ERROR] Order rejected on {symbol}: {res.get('msg')} (Code: {res.get('code')})")
        except Exception as e:
            print(f"[ERROR] Place order exception: {e}")
        return None

    def check_order_filled(self, symbol, order_id):
        try:
            path = f"/api/v5/trade/order?instId={symbol}&ordId={order_id}"
            headers = self.get_signed_headers("GET", path)
            res = requests.get(BASE_URL + path, headers=headers, timeout=10).json()
            if res.get("code") == "0" and res.get("data"):
                if res["data"][0].get("state") == "filled":
                    return True
        except Exception:
            pass
        return False

    def run(self):
        print(f"[ULTRA-INSTITUTIONAL-BOT] النظام الخارق يعمل بأقصى طاقة (فحص كل {CHECK_INTERVAL} ثوانٍ)...")
        while True:
            try:
                avail_balance = self.get_balance()
                active_pos_val = sum(self.position_sizes_usdt.values())
                total_portfolio = avail_balance + active_pos_val

                # 1. متابعة الصفقات المفتوحة
                for symbol in SYMBOLS:
                    if self.positions[symbol] == "LONG":
                        current_price = self.get_ticker_price(symbol)
                        if not current_price:
                            continue

                        pnl_pct = (current_price - self.entry_prices[symbol]) / self.entry_prices[symbol]
                        drawdown_pct = (self.entry_prices[symbol] - current_price) / self.entry_prices[symbol]

                        print(f"[MONITORING {symbol}] متوسط التكلفة: {self.entry_prices[symbol]} | الحالي: {current_price} | PnL: {pnl_pct*100:.2f}%")

                        # جني الأرباح الفوري المضمون عند 0.8%
                        if pnl_pct >= TAKE_PROFIT_PCT:
                            print(f"[ULTRA TAKE PROFIT] تم تحقيق الهدف ({pnl_pct*100:.2f}%) على {symbol}! تنفيذ بيع فوري...")
                            self.place_order(symbol, "sell", current_price, self.position_sizes_asset[symbol], is_sz=True)
                            self.positions[symbol] = None
                            self.position_sizes_usdt[symbol] = 0.0
                            self.position_sizes_asset[symbol] = 0.0
                            self.dca_used[symbol] = False
                            time.sleep(2)
                            continue

                        # تأمين نقطة الدخول عند 0.5%
                        if pnl_pct >= 0.005 and not self.breakeven_activated[symbol]:
                            self.breakeven_activated[symbol] = True
                            self.active_stop_loss_pct[symbol] = 0.0000
                            print(f"[BREAKEVEN SECURED] تم تأمين نقطة الدخول لـ {symbol}.")

                        # وقف الخسارة الحازم
                        if drawdown_pct >= self.active_stop_loss_pct[symbol]:
                            print(f"[STOP LOSS TRIGGER] الخروج الفوري لحماية المحفظة في {symbol}...")
                            self.place_order(symbol, "sell", current_price, self.position_sizes_asset[symbol], is_sz=True)
                            self.positions[symbol] = None
                            self.position_sizes_usdt[symbol] = 0.0
                            self.position_sizes_asset[symbol] = 0.0
                            self.dca_used[symbol] = False
                            time.sleep(2)
                            continue

                        # التعزيز الذكي الآمن لمرة واحدة (30%)
                        curr_ratio = self.position_sizes_usdt[symbol] / total_portfolio if total_portfolio > 0 else 0
                        if drawdown_pct >= DCA_TRIGGER_PCT and not self.dca_used[symbol] and curr_ratio < MAX_SINGLE_ASSET_PCT:
                            print(f"[ULTRA DCA] تفعيل التعزيز الذكي الآمن لمرة واحدة لـ {symbol}...")
                            dca_budget = self.position_sizes_usdt[symbol] * 0.3
                            res_id = self.place_order(symbol, "buy", current_price, dca_budget, is_sz=False)
                            if res_id:
                                time.sleep(2)
                                if self.check_order_filled(symbol, res_id):
                                    dca_qty = dca_budget / current_price
                                    total_c = self.position_sizes_usdt[symbol] + dca_budget
                                    total_s = self.position_sizes_asset[symbol] + dca_qty
                                    self.entry_prices[symbol] = total_c / total_s
                                    self.position_sizes_usdt[symbol] = total_c
                                    self.position_sizes_asset[symbol] = total_s
                                    self.dca_used[symbol] = True
                                    print(f"[DCA SUCCESS] متوسط السعر الجديد لـ {symbol}: {self.entry_prices[symbol]}")
                    else:
                        self.positions[symbol] = None
                        self.position_sizes_usdt[symbol] = 0.0
                        self.position_sizes_asset[symbol] = 0.0

                # 2. الماسح الذكي للفرص الذهبية
                print(f"[SCANNER] الكاش المتاح: {avail_balance:.2f} | إجمالي المحفظة: {total_portfolio:.2f} USDT")

                for symbol in SYMBOLS:
                    if self.positions[symbol] is None:
                        current_price = self.get_ticker_price(symbol)
                        if not current_price:
                            continue

                        if (self.position_sizes_usdt[symbol] / total_portfolio >= MAX_SINGLE_ASSET_PCT) if total_portfolio > 0 else False:
                            continue

                        trade_budget = (total_portfolio * ALLOCATION_PCT) / 3
                        if avail_balance < trade_budget:
                            continue  

                        if self.check_market_conditions(symbol):
                            print(f"[GOLDEN ENTRY] فرصة ذهبية مؤكدة بنسبة 100% على {symbol}! جاري التنفيذ...")
                            order_id = self.place_order(symbol, "buy", current_price, trade_budget, is_sz=False)
                            if order_id:
                                for _ in range(3):
                                    time.sleep(2)
                                    if self.check_order_filled(symbol, order_id):
                                        self.positions[symbol] = "LONG"
                                        self.entry_prices[symbol] = current_price
                                        self.position_sizes_usdt[symbol] = trade_budget
                                        self.position_sizes_asset[symbol] = round(trade_budget / current_price, 6)
                                        self.dca_used[symbol] = False
                                        self.breakeven_activated[symbol] = False
                                        self.active_stop_loss_pct[symbol] = STOP_LOSS_PCT
                                        print(f"[ACTIVE SUCCESS] دخلت صفقة {symbol} بنجاح بسعر {current_price}")
                                        break
                        else:
                            print(f"[SLEEP] البوت يراقب السوق بهدوء تامة لـ {symbol}...")
                    
                    time.sleep(2)

                time.sleep(CHECK_INTERVAL)
            except Exception as e:
                print(f"[CRITICAL ERROR] Loop exception: {e}")
                time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    bot = UltimateInstitutionalBot()
    bot.run()
    
