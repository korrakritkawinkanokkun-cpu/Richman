"""
config.py — ตั้งค่าทั้งหมดที่เดียว

Token/Chat ID อ่านจาก environment variable ก่อน (สำหรับ GitHub Actions / cloud)
ถ้าไม่มี env ค่อย fallback มาใช้ค่าในไฟล์นี้ (สำหรับรัน local บนเครื่องตัวเอง)
"""
import os

# --- Telegram ---
# บน GitHub Actions: ตั้งใน repo Settings > Secrets ชื่อ TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS
# บน local: แก้ค่า fallback ด้านล่างได้เลย
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "ใส่ BOT_TOKEN ของคุณที่นี่")

# TELEGRAM_CHAT_IDS: บน env ใส่เป็น string คั่นด้วย comma เช่น "123456,-100987654"
# บน local ใช้ list ปกติ
_chat_env = os.environ.get("TELEGRAM_CHAT_IDS", "")
if _chat_env:
    TELEGRAM_CHAT_IDS = [c.strip() for c in _chat_env.split(",") if c.strip()]
else:
    TELEGRAM_CHAT_IDS = ["ใส่ CHAT_ID ของคุณที่นี่"]   # แก้ตรงนี้สำหรับรัน local

# --- US universe ---
US_INCLUDE_NYSE_AMEX = True

# --- SET universe ---
SET_LOCAL_FILE = None

# --- Liquidity filter (Stage 1) ---
SET_MIN_PRICE = 1.0
SET_MIN_AVG_VOLUME = 1_000_000
US_MIN_PRICE = 5.0
US_MIN_AVG_VOLUME = 500_000

# --- Technical scan (Stage 2) ---
MIN_SCORE_TO_ALERT = 3
LOOKBACK_DAYS_FOR_RANGE = 15
HISTORY_PERIOD = "6mo"
ENABLE_RSI_DIVERGENCE = True   # ตรวจ RSI bullish divergence (ทรง low กำลังกลับตัว)

# --- ชั้นเสริม (Stage 3) ---
ENABLE_FUNDAMENTAL = True
ENABLE_NEWS = True
NEWS_MAX_ITEMS = 3

# --- Performance ---
LIQUIDITY_BATCH_SIZE = 50
STAGE2_DELAY_SEC = 0.5
ENABLE_UNIVERSE_CACHE = True

# --- Resume ---
ENABLE_RESUME = True

# --- Logging ---
LOG_FILE = "scanner.log"
