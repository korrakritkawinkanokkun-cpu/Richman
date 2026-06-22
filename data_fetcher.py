"""
data_fetcher.py
- ดึงรายชื่อ ticker ทั้งตลาด:
    * US: Nasdaq + NYSE + AMEX (จาก nasdaqtrader.com 2 ไฟล์ทางการ)
    * SET: ทั้ง SET + mai (จาก stockanalysis.com, มี fallback ใส่ไฟล์เอง)
- กรอง liquidity (ราคา/volume) ก่อนดึงข้อมูลละเอียด
- ดึงราคาประวัติศาสตร์ผ่าน yfinance พร้อม retry
"""

import time
import io
import os
import logging
import pandas as pd
import yfinance as yf
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("data_fetcher")

# --- US (ทางการ nasdaqtrader.com) ---
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"  # NYSE/AMEX/อื่นๆ

# --- SET ---
SET_STOCKANALYSIS_URL = "https://stockanalysis.com/list/stock-exchange-of-thailand/"
# fallback: ถ้าวางไฟล์ CSV/Excel รายชื่อหุ้น SET ไว้เอง ใส่ path ที่ config แล้วส่งเข้ามา

REQUEST_TIMEOUT = 20
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 5
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StockScanner/1.0)"}


def _get_with_retry(url: str):
    """GET request พร้อม retry คืน response object หรือ None"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except Exception as e:
            log.warning(f"GET {url} ล้มเหลว (ครั้งที่ {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC)
    return None


# ---------------------------------------------------------------------------
# US universe (Nasdaq + NYSE + AMEX)
# ---------------------------------------------------------------------------

def _parse_nasdaq_listed(text: str) -> pd.DataFrame:
    """parse nasdaqlisted.txt -> DataFrame ของหุ้นจริง (ตัด ETF/test)"""
    df = pd.read_csv(io.StringIO(text), sep="|")
    df = df[df["Symbol"].notna()]
    df = df[~df["Symbol"].astype(str).str.contains("File Creation Time", na=False)]
    df = df[df["Test Issue"] == "N"]
    df = df[df["ETF"] == "N"]
    return df[["Symbol"]].rename(columns={"Symbol": "ticker"})


def _parse_other_listed(text: str) -> pd.DataFrame:
    """
    parse otherlisted.txt (NYSE/AMEX/อื่นๆ)
    คอลัมน์: ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
    Exchange code: A=NYSE American(AMEX), N=NYSE, P=NYSE ARCA, Z=BATS, V=IEX
    """
    df = pd.read_csv(io.StringIO(text), sep="|")
    sym_col = "ACT Symbol" if "ACT Symbol" in df.columns else "CQS Symbol"
    df = df[df[sym_col].notna()]
    df = df[~df[sym_col].astype(str).str.contains("File Creation Time", na=False)]
    if "Test Issue" in df.columns:
        df = df[df["Test Issue"] == "N"]
    if "ETF" in df.columns:
        df = df[df["ETF"] != "Y"]  # ตัด ETF (บางแถวเป็น NaN เก็บไว้)
    return df[[sym_col]].rename(columns={sym_col: "ticker"})


def _clean_us_tickers(tickers: list) -> list:
    """
    ตัด ticker ที่มีสัญลักษณ์พิเศษซึ่งมักเป็น preferred/warrant/unit
    และแปลง format ให้ตรงกับ yfinance (ใช้ - แทน . ใน class share เช่น BRK.B -> BRK-B)
    """
    cleaned = []
    for t in tickers:
        t = str(t).strip().upper()
        if not t or " " in t:
            continue
        # ตัด warrant/unit/right/preferred ที่มี suffix ตัวอักษรหลังจุด/+/^/$ ฯลฯ
        if any(c in t for c in ["$", "^", "+", "=", "~"]):
            continue
        # yfinance ใช้ - แทน . สำหรับ class shares (BRK.B -> BRK-B)
        t = t.replace(".", "-")
        cleaned.append(t)
    return sorted(set(cleaned))


def get_us_universe(include_nyse_amex: bool = True) -> list:
    """
    ดึงรายชื่อหุ้น US ทั้งหมด: Nasdaq + (NYSE/AMEX ถ้า include_nyse_amex=True)
    คืน list ของ ticker symbol พร้อมใช้กับ yfinance
    """
    frames = []

    resp = _get_with_retry(NASDAQ_LISTED_URL)
    if resp is not None:
        try:
            frames.append(_parse_nasdaq_listed(resp.text))
            log.info("parse nasdaqlisted.txt สำเร็จ")
        except Exception as e:
            log.error(f"parse nasdaqlisted.txt ล้มเหลว: {e}")

    if include_nyse_amex:
        resp2 = _get_with_retry(OTHER_LISTED_URL)
        if resp2 is not None:
            try:
                frames.append(_parse_other_listed(resp2.text))
                log.info("parse otherlisted.txt (NYSE/AMEX) สำเร็จ")
            except Exception as e:
                log.error(f"parse otherlisted.txt ล้มเหลว: {e}")

    if not frames:
        log.error("ดึง US universe ไม่สำเร็จเลย")
        return []

    all_df = pd.concat(frames, ignore_index=True)
    tickers = _clean_us_tickers(all_df["ticker"].tolist())
    log.info(f"US universe รวม: {len(tickers)} tickers (Nasdaq+NYSE+AMEX)")
    return tickers


# ---------------------------------------------------------------------------
# SET universe (SET + mai)
# ---------------------------------------------------------------------------

def get_set_universe(local_file: str = None) -> list:
    """
    ดึงรายชื่อหุ้น SET ทั้งหมด
    ลำดับการพยายาม:
      1. ถ้าระบุ local_file (CSV/Excel ที่ดาวน์โหลดจาก set.or.th เอง) -> อ่านจากไฟล์ (เสถียรสุด)
      2. ดึงจาก stockanalysis.com (scrape ตาราง)
    คืน list ของ ticker (ไม่มี .BK — เติมตอนเรียก yfinance)
    """
    # --- 1) ไฟล์ local (แนะนำถ้าอยากเสถียร 100%) ---
    if local_file and os.path.exists(local_file):
        try:
            if local_file.lower().endswith((".xlsx", ".xls")):
                df = pd.read_excel(local_file)
            else:
                df = pd.read_csv(local_file)
            symbol_col = next((c for c in df.columns
                               if str(c).lower() in ("symbol", "ticker", "หลักทรัพย์", "ชื่อย่อ")), None)
            if symbol_col is None:
                symbol_col = df.columns[0]  # เดาเป็นคอลัมน์แรก
            tickers = df[symbol_col].dropna().astype(str).str.strip().str.upper().unique().tolist()
            tickers = [t for t in tickers if t and " " not in t]
            log.info(f"อ่าน SET universe จากไฟล์ {local_file}: {len(tickers)} tickers")
            return sorted(set(tickers))
        except Exception as e:
            log.warning(f"อ่านไฟล์ SET local ล้มเหลว: {e} -> ลอง scrape เว็บแทน")

    # --- 2) stockanalysis.com ---
    resp = _get_with_retry(SET_STOCKANALYSIS_URL)
    if resp is not None:
        try:
            tables = pd.read_html(io.StringIO(resp.text))
            df = tables[0]
            symbol_col = next((c for c in df.columns if "symbol" in str(c).lower()), None)
            if symbol_col is None:
                raise ValueError("ไม่พบคอลัมน์ Symbol — โครงสร้างเว็บอาจเปลี่ยน")
            tickers = df[symbol_col].dropna().astype(str).str.strip().str.upper().unique().tolist()
            tickers = [t for t in tickers if t and " " not in t]
            log.info(f"ดึง SET universe จาก stockanalysis.com: {len(tickers)} tickers")
            return sorted(set(tickers))
        except Exception as e:
            log.error(f"scrape SET universe ล้มเหลว: {e}")

    log.error("ดึง SET universe ไม่สำเร็จ — แนะนำดาวน์โหลด Excel จาก set.or.th แล้วใส่ path ใน config")
    return []


# ---------------------------------------------------------------------------
# Liquidity pre-filter (Stage 1)
# ---------------------------------------------------------------------------

def liquidity_filter(tickers: list, market: str,
                     min_price: float, min_avg_volume: float,
                     batch_size: int = 50) -> list:
    """
    ดึงราคา+volume แบบเบา (10 วัน) เป็น batch เพื่อกรองหุ้นเล็ก/ไม่มีสภาพคล่อง
    market: 'SET' (เติม .BK) หรือ 'US' (ไม่เติม)
    """
    survivors = []
    suffix = ".BK" if market.upper() == "SET" else ""
    full_tickers = [f"{t}{suffix}" for t in tickers]

    total = len(full_tickers)
    for i in range(0, total, batch_size):
        batch = full_tickers[i:i + batch_size]
        data = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                data = yf.download(batch, period="10d", interval="1d",
                                   group_by="ticker", progress=False, threads=True)
                break
            except Exception as e:
                log.warning(f"liquidity batch {i} ล้มเหลว (ครั้งที่ {attempt}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF_SEC)

        if data is None:
            continue

        for t in batch:
            try:
                sub = data[t] if len(batch) > 1 else data
                if sub.empty or "Close" not in sub:
                    continue
                last_price = sub["Close"].dropna().iloc[-1]
                avg_vol = sub["Volume"].dropna().mean()
                if last_price >= min_price and avg_vol >= min_avg_volume:
                    survivors.append(t)
            except Exception:
                continue

        log.info(f"[{market}] liquidity: {min(i + batch_size, total)}/{total} "
                 f"(ผ่านสะสม {len(survivors)})")
        time.sleep(1)

    log.info(f"[{market}] liquidity filter เสร็จ: {len(survivors)}/{total} ตัวผ่าน")
    return survivors


# ---------------------------------------------------------------------------
# Detailed history fetch (Stage 2 input)
# ---------------------------------------------------------------------------

def fetch_history(ticker: str, period: str = "6mo", interval: str = "1d"):
    """ดึงราคาประวัติศาสตร์ของ ticker เดียว พร้อม retry"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            df = yf.Ticker(ticker).history(period=period, interval=interval)
            if df is None or df.empty:
                return None
            return df
        except Exception as e:
            log.warning(f"fetch_history({ticker}) ล้มเหลว (ครั้งที่ {attempt}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC)
    return None


if __name__ == "__main__":
    # ต้องรันบนเครื่องที่ต่อเน็ตได้จริง (ไม่ใช่ sandbox)
    print("=== ทดสอบดึง US universe (Nasdaq+NYSE+AMEX) ===")
    us = get_us_universe(include_nyse_amex=True)
    print(f"ได้ {len(us)} tickers, ตัวอย่าง: {us[:15]}")

    print("\n=== ทดสอบดึง SET universe ===")
    se = get_set_universe()
    print(f"ได้ {len(se)} tickers, ตัวอย่าง: {se[:15]}")
