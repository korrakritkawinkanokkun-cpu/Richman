"""
main_scanner.py — สคริปต์หลัก
  python3 main_scanner.py --market SET
  python3 main_scanner.py --market US

Pipeline:
  Stage 0: โหลด universe (มี cache รายวัน)
  Stage 1: liquidity filter (กรองหุ้นเล็ก/ไม่มีสภาพคล่อง)
  Stage 2: technical scan (EMA/RSI/MACD/breakout) + resume
  Stage 3: เสริม fundamental + news เฉพาะตัวที่เข้าเกณฑ์
  Stage 4: ส่ง Telegram (หลาย chat/กลุ่ม)
"""

import argparse
import logging
import time
import sys

import config
from data_fetcher import get_set_universe, get_us_universe, liquidity_filter, fetch_history
from indicators import detect_setup, is_actionable
from telegram_notifier import send_to_all, format_alert_message
from universe_cache import get_universe_cached
from fundamental import fetch_fundamentals, format_fundamental_line
from news_fetcher import fetch_latest_news, format_news_block
from resume_tracker import load_progress, save_progress, clear_old_progress

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("main_scanner")


def load_universe(market: str) -> list:
    if market == "SET":
        fetch_fn = lambda: get_set_universe(local_file=config.SET_LOCAL_FILE)
    else:  # US
        fetch_fn = lambda: get_us_universe(include_nyse_amex=config.US_INCLUDE_NYSE_AMEX)

    if config.ENABLE_UNIVERSE_CACHE:
        return get_universe_cached(market, fetch_fn)
    return fetch_fn()


def enrich(ticker: str) -> dict:
    """ดึง fundamental + news เสริม (เฉพาะตัวที่ผ่าน technical)"""
    extra = {}
    if config.ENABLE_FUNDAMENTAL:
        try:
            fund = fetch_fundamentals(ticker)
            extra["fundamental_line"] = format_fundamental_line(fund)
        except Exception as e:
            log.warning(f"enrich fundamental {ticker}: {e}")
    if config.ENABLE_NEWS:
        try:
            news = fetch_latest_news(ticker, max_items=config.NEWS_MAX_ITEMS)
            extra["news_block"] = format_news_block(news)
        except Exception as e:
            log.warning(f"enrich news {ticker}: {e}")
    return extra


def run_scan(market: str, test_mode: bool = False, limit: int = 0):
    market = market.upper()
    start = time.time()
    log.info(f"========== เริ่มสแกน {market} ==========")
    clear_old_progress()

    # Stage 0: universe
    if market not in ("SET", "US"):
        log.error(f"ไม่รู้จักตลาด: {market}")
        return
    universe = load_universe(market)
    if test_mode:
        # โหมดทดสอบ: ใช้หุ้นยอดนิยมไม่กี่ตัวที่รู้ว่ามีข้อมูลแน่ๆ
        if market == "SET":
            universe = ["PTT", "AOT", "CPALL", "ADVANC", "KBANK"]
        else:
            universe = ["AAPL", "NVDA", "MSFT", "TSLA", "AMZN"]
        log.info(f"[{market}] 🧪 โหมดทดสอบ: สแกนแค่ {len(universe)} ตัว")
    if not universe:
        send_to_all(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_IDS,
                    f"⚠️ {market} Scan: โหลดรายชื่อหุ้นไม่สำเร็จ")
        return
    min_price = config.SET_MIN_PRICE if market == "SET" else config.US_MIN_PRICE
    min_vol = config.SET_MIN_AVG_VOLUME if market == "SET" else config.US_MIN_AVG_VOLUME
    log.info(f"[{market}] universe: {len(universe)} ตัว")

    # Stage 1: liquidity
    survivors = liquidity_filter(universe, market, min_price, min_vol,
                                 batch_size=config.LIQUIDITY_BATCH_SIZE)
    if not survivors:
        log.warning(f"[{market}] ไม่มีตัวผ่าน liquidity — จบ")
        return

    if limit > 0:
        survivors = survivors[:limit]
        log.info(f"[{market}] จำกัดที่ {limit} ตัวแรก")

    # Resume: ข้ามตัวที่ทำไปแล้ววันนี้
    done = load_progress(market) if (config.ENABLE_RESUME and not test_mode) else set()
    if done:
        log.info(f"[{market}] resume: ข้าม {len(done)} ตัวที่สแกนแล้ววันนี้")
        survivors = [t for t in survivors if t not in done]

    # Stage 2+3: technical scan + enrich
    results = []
    for idx, ticker in enumerate(survivors, 1):
        df = fetch_history(ticker, period=config.HISTORY_PERIOD)
        if df is not None:
            setup = detect_setup(df, lookback_range=config.LOOKBACK_DAYS_FOR_RANGE)
            if is_actionable(setup, min_score=config.MIN_SCORE_TO_ALERT):
                row = {"ticker": ticker, "setup": setup}
                row.update(enrich(ticker))  # Stage 3 เสริมเฉพาะตัวที่ผ่าน
                results.append(row)
                log.info(f"  [{idx}/{len(survivors)}] {ticker} -> เข้าเกณฑ์ (score {setup['score']})")
        done.add(ticker)
        if config.ENABLE_RESUME and idx % 25 == 0:
            save_progress(market, done)  # เซฟ progress เป็นระยะ
        time.sleep(config.STAGE2_DELAY_SEC)

    if config.ENABLE_RESUME:
        save_progress(market, done)

    # Stage 4: ส่ง Telegram
    msg = format_alert_message(market, results)
    send_to_all(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_IDS, msg)

    log.info(f"[{market}] พบ {len(results)} ตัวเข้าเกณฑ์ | "
             f"ใช้เวลา {(time.time()-start)/60:.1f} นาที")
    log.info(f"========== สแกน {market} เสร็จ ==========")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="สแกนหุ้น SET/US ตามเกณฑ์เทคนิค+พื้นฐาน+ข่าว")
    parser.add_argument("--market", required=True, choices=["SET", "US"])
    parser.add_argument("--test", action="store_true",
                        help="โหมดทดสอบ: สแกนแค่ไม่กี่ตัวเพื่อเช็คว่าระบบ/Telegram ทำงาน")
    parser.add_argument("--limit", type=int, default=0,
                        help="จำกัดจำนวนหุ้นที่สแกน (0 = ไม่จำกัด)")
    args = parser.parse_args()
    run_scan(args.market, test_mode=args.test, limit=args.limit)
