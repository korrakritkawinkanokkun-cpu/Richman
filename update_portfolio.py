"""
update_portfolio.py
====================
อ่านชีต Holdings จาก Google Sheets -> ดึงราคาปัจจุบันของแต่ละสินทรัพย์
(SET Stock / US Stock / Crypto / Gold / Fund) -> เขียนราคากลับเข้า Holdings
-> คำนวณยอดรวมแต่ละ owner -> append เข้า DailyHistory

รันผ่าน GitHub Actions วันละ 1 ครั้ง (แนะนำ 17:00 เวลาไทย)

ENV ที่ต้องตั้งไว้เป็น GitHub Secret:
    GOOGLE_SHEETS_CREDS   -> เนื้อหา JSON เต็มของ Service Account (ตัวเดิมที่ใช้กับ stock_scanner)
    PORTFOLIO_SHEET_ID    -> Sheet ID ของไฟล์ Portfolio Dashboard (เอามาจาก URL ของ Sheet)
"""

import os
import json
import datetime
from zoneinfo import ZoneInfo

import gspread
from google.oauth2.service_account import Credentials
import yfinance as yf
import ccxt

BANGKOK_TZ = ZoneInfo("Asia/Bangkok")
GOLD_PREMIUM_USD = 2.0          # ค่าพรีเมียมนำเข้าทอง (USD/oz) ปรับได้ตามจริง
GOLD_965_FACTOR = 32.148 * 0.965 / 65.6   # แปลง spot (USD/oz, 99.99%) -> บาทไทย/บาททอง 96.5%

HOLDINGS_SHEET = "Holdings"
HISTORY_SHEET = "DailyHistory"

# ----------------------------------------------------------------------
# 1) Google Sheets connection
# ----------------------------------------------------------------------

def get_gspread_client():
    creds_json = json.loads(os.environ["GOOGLE_SHEETS_CREDS"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    return gspread.authorize(creds)


# ----------------------------------------------------------------------
# 2) Price fetchers — ต่างกันตาม asset_type
# ----------------------------------------------------------------------

def get_usdthb_rate() -> float:
    """ดึงเรท USD/THB ปัจจุบันจาก yfinance"""
    t = yf.Ticker("THB=X")
    hist = t.history(period="1d")
    if hist.empty:
        raise RuntimeError("ดึงเรท USD/THB ไม่ได้ (yfinance คืนค่าว่าง)")
    return float(hist["Close"].iloc[-1])


def get_set_stock_price(symbol: str) -> float:
    """หุ้น SET ต่อท้าย .BK เช่น EGCO -> EGCO.BK"""
    t = yf.Ticker(f"{symbol}.BK")
    hist = t.history(period="1d")
    if hist.empty:
        raise RuntimeError(f"ดึงราคา SET stock {symbol} ไม่ได้")
    return float(hist["Close"].iloc[-1])


def get_us_stock_price(symbol: str) -> float:
    t = yf.Ticker(symbol)
    hist = t.history(period="1d")
    if hist.empty:
        raise RuntimeError(f"ดึงราคา US stock {symbol} ไม่ได้")
    return float(hist["Close"].iloc[-1])


def get_crypto_price(symbol: str) -> float:
    """ราคา crypto เทียบ USD ผ่าน Binance (ccxt) เช่น BTC -> BTC/USDT"""
    exchange = ccxt.binance()
    ticker = exchange.fetch_ticker(f"{symbol}/USDT")
    return float(ticker["last"])


def get_gold_price_965_thb(fx_rate: float) -> float:
    """
    ราคาทองคำแท่ง 96.5% (บาท/บาททอง) แปลงจากราคาทองโลก (Spot, 99.99%)
    สูตรอ้างอิงจากหลักการคำนวณทั่วไปของสมาคมค้าทองคำ:
        ราคาทองไทย = (Spot_USD_per_oz + premium) x fx_rate x (32.148 x 0.965 / 65.6)
    หมายเหตุ: เป็นราคา "ประมาณ" ใกล้เคียงราคาสมาคมค้าทองคำ ไม่ใช่ราคาประกาศจริง
    เพราะราคาจริงสมาคมฯ ปรับตามดุลยพินิจ/สเปรดอีกชั้นหนึ่ง
    """
    t = yf.Ticker("GC=F")
    hist = t.history(period="1d")
    if hist.empty:
        raise RuntimeError("ดึงราคาทองโลก (GC=F) ไม่ได้")
    spot_usd_oz = float(hist["Close"].iloc[-1])
    return (spot_usd_oz + GOLD_PREMIUM_USD) * fx_rate * GOLD_965_FACTOR


def get_thai_fund_nav(symbol: str) -> float:
    """
    NAV กองทุนรวมไทย (เช่น Thai ESG ของ KAsset) — ไม่มี API สาธารณะที่ scrape ตรงได้ง่าย
    ต้องปรับ URL ตรงนี้เองหลังเช็คจากเว็บ KAsset (ดูวิธีหา URL จริงใน README)

    ตัวอย่าง URL รูปแบบที่ KAsset ใช้ (ต้องตรวจสอบ/ปรับ endpoint จริงอีกครั้ง):
        https://www.kasikornasset.com/.../download-pastnav.aspx?codes={symbol}
    หน้านี้โหลดด้วย JavaScript จึง fetch ตรงไม่ได้ -> แนะนำเปิด DevTools (F12)
    แท็บ Network ตอนกดปุ่มโหลด NAV บนเว็บจริง จะเห็น request ที่เป็น JSON/CSV ตรงๆ
    ให้เอา URL นั้นมาแทนที่ฟังก์ชันนี้
    """
    raise NotImplementedError(
        f"ยังไม่ได้ตั้งค่าแหล่งดึง NAV ของกองทุน {symbol} "
        "— ดูวิธีหา endpoint จริงใน README ส่วน 'Thai Fund NAV'"
    )


def fetch_price(asset_type: str, symbol: str, fx_rate_cache: dict) -> tuple[float, float]:
    """
    คืนค่า (current_price, fx_rate) ตาม asset_type
    current_price = ราคาในสกุลเงินต้นทาง, fx_rate = ตัวคูณแปลงเป็น THB
    """
    if "usdthb" not in fx_rate_cache:
        fx_rate_cache["usdthb"] = get_usdthb_rate()
    usdthb = fx_rate_cache["usdthb"]

    if asset_type == "SET Stock":
        return get_set_stock_price(symbol), 1.0
    elif asset_type == "US Stock":
        return get_us_stock_price(symbol), usdthb
    elif asset_type == "Crypto":
        return get_crypto_price(symbol), usdthb
    elif asset_type == "Gold":
        # เก็บ current_price เป็นราคาทองแท่ง 96.5% บาทไทยตรงๆ (fx_rate = 1.0
        # เพราะแปลงเป็น THB ในฟังก์ชันนี้เรียบร้อยแล้ว)
        return get_gold_price_965_thb(usdthb), 1.0
    elif asset_type == "Fund":
        return get_thai_fund_nav(symbol), 1.0
    else:
        raise ValueError(f"ไม่รู้จัก asset_type: {asset_type}")


# ----------------------------------------------------------------------
# 3) Main update flow
# ----------------------------------------------------------------------

def update_holdings(ws_holdings):
    rows = ws_holdings.get_all_records()
    headers = ws_holdings.row_values(1)
    col = {name: idx + 1 for idx, name in enumerate(headers)}

    fx_rate_cache: dict = {}
    now_str = datetime.datetime.now(BANGKOK_TZ).strftime("%Y-%m-%d %H:%M")

    owner_totals: dict[str, dict[str, float]] = {}

    for i, row in enumerate(rows):
        sheet_row = i + 2  # row 1 = header
        owner = row.get("owner", "").strip()
        asset_type = row.get("asset_type", "").strip()
        symbol = row.get("symbol", "").strip()
        quantity = float(row.get("quantity") or 0)
        avg_cost = float(row.get("avg_cost") or 0)

        if not owner or not asset_type or not symbol:
            continue

        try:
            current_price, fx_rate = fetch_price(asset_type, symbol, fx_rate_cache)
        except NotImplementedError as e:
            print(f"[SKIP] {owner}/{symbol}: {e}")
            continue
        except Exception as e:
            print(f"[ERROR] {owner}/{symbol}: ดึงราคาไม่สำเร็จ -> {e}")
            continue

        ws_holdings.update_cell(sheet_row, col["current_price"], current_price)
        ws_holdings.update_cell(sheet_row, col["fx_rate"], fx_rate)
        ws_holdings.update_cell(sheet_row, col["last_updated"], now_str)

        market_value_thb = quantity * current_price * fx_rate
        cost_value_thb = quantity * avg_cost * fx_rate

        bucket = owner_totals.setdefault(owner, {"market_value": 0.0, "cost_value": 0.0})
        bucket["market_value"] += market_value_thb
        bucket["cost_value"] += cost_value_thb

        print(f"[OK] {owner}/{symbol}: price={current_price:.2f} fx={fx_rate:.4f} "
              f"mv_thb={market_value_thb:,.0f}")

    return owner_totals


def append_daily_history(ws_history, owner_totals: dict):
    today_str = datetime.datetime.now(BANGKOK_TZ).strftime("%Y-%m-%d")
    rows_to_append = []
    for owner, totals in owner_totals.items():
        mv = totals["market_value"]
        cv = totals["cost_value"]
        unrealized_thb = mv - cv
        unrealized_pct = (unrealized_thb / cv) if cv else ""
        rows_to_append.append([today_str, owner, mv, cv, unrealized_thb, unrealized_pct])

    if rows_to_append:
        ws_history.append_rows(rows_to_append, value_input_option="USER_ENTERED")
        print(f"[OK] เพิ่ม {len(rows_to_append)} แถวลง DailyHistory ({today_str})")


def main():
    gc = get_gspread_client()
    sh = gc.open_by_key(os.environ["PORTFOLIO_SHEET_ID"])

    ws_holdings = sh.worksheet(HOLDINGS_SHEET)
    ws_history = sh.worksheet(HISTORY_SHEET)

    owner_totals = update_holdings(ws_holdings)
    append_daily_history(ws_history, owner_totals)


if __name__ == "__main__":
    main()
