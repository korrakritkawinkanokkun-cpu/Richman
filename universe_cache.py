"""
universe_cache.py
Cache รายชื่อหุ้น (universe) ลงไฟล์ JSON รายวัน
- ถ้ามี cache ของวันนี้แล้ว -> โหลดจากไฟล์ (ไม่ต้องดึงใหม่)
- ถ้าไม่มี/เก่ากว่าวันนี้ -> ดึงใหม่แล้วเซฟ
ช่วยลดเวลาและภาระตอนรันหลายรอบต่อวัน (รายชื่อหุ้นไม่เปลี่ยนระหว่างวัน)
"""

import os
import json
import logging
from datetime import datetime

log = logging.getLogger("universe_cache")

CACHE_DIR = "cache"


def _cache_path(market: str) -> str:
    return os.path.join(CACHE_DIR, f"universe_{market.upper()}.json")


def load_cached_universe(market: str) -> list | None:
    """โหลด universe จาก cache ถ้าเป็นของวันนี้ คืน None ถ้าไม่มี/เก่า"""
    path = _cache_path(market)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        today = datetime.now().strftime("%Y-%m-%d")
        if data.get("date") == today and data.get("tickers"):
            log.info(f"[{market}] ใช้ universe จาก cache วันนี้: {len(data['tickers'])} ตัว")
            return data["tickers"]
        log.info(f"[{market}] cache เก่า (วันที่ {data.get('date')}) -> จะดึงใหม่")
        return None
    except Exception as e:
        log.warning(f"[{market}] อ่าน cache ล้มเหลว: {e}")
        return None


def save_universe_cache(market: str, tickers: list) -> None:
    """เซฟ universe ลง cache พร้อม timestamp วันนี้"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(market)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "count": len(tickers),
                "tickers": tickers,
            }, f, ensure_ascii=False, indent=2)
        log.info(f"[{market}] เซฟ universe cache: {len(tickers)} ตัว -> {path}")
    except Exception as e:
        log.warning(f"[{market}] เซฟ cache ล้มเหลว: {e}")


def get_universe_cached(market: str, fetch_func) -> list:
    """
    wrapper: ลองโหลด cache ก่อน ถ้าไม่มีค่อยเรียก fetch_func() แล้วเซฟ
    fetch_func: ฟังก์ชันที่คืน list ของ ticker (เช่น lambda: get_us_universe())
    """
    cached = load_cached_universe(market)
    if cached is not None:
        return cached
    tickers = fetch_func()
    if tickers:
        save_universe_cache(market, tickers)
    return tickers


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # ทดสอบด้วย fetch_func ปลอม
    fake_fetch = lambda: ["AAA", "BBB", "CCC"]
    print("รอบแรก (ควรดึงใหม่+เซฟ):")
    r1 = get_universe_cached("TEST", fake_fetch)
    print("  ได้:", r1)
    print("รอบสอง (ควรโหลดจาก cache):")
    r2 = get_universe_cached("TEST", lambda: ["ไม่ควรเห็นอันนี้"])
    print("  ได้:", r2)
    assert r2 == ["AAA", "BBB", "CCC"], "cache ไม่ทำงาน!"
    print("✅ cache ทำงานถูกต้อง")
    # ลบไฟล์ทดสอบ
    os.remove(_cache_path("TEST"))
