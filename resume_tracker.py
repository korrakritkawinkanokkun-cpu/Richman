"""
resume_tracker.py
ติดตามว่าหุ้นตัวไหนสแกน Stage 2 ไปแล้วในวันนี้ (ต่อตลาด ต่อรอบเวลา)
ถ้าสคริปต์ถูก interrupt แล้วรันใหม่ จะข้ามตัวที่ทำไปแล้ว ไม่ต้องเริ่มใหม่หมด
เก็บเป็นไฟล์ JSON รายวัน
"""

import os
import json
import logging
from datetime import datetime

log = logging.getLogger("resume_tracker")

PROGRESS_DIR = "progress"


def _progress_path(market: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(PROGRESS_DIR, f"progress_{market.upper()}_{today}.json")


def load_progress(market: str) -> set:
    """โหลดรายชื่อ ticker ที่สแกนไปแล้ววันนี้ คืนเป็น set"""
    path = _progress_path(market)
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("done", []))
    except Exception as e:
        log.warning(f"อ่าน progress ล้มเหลว: {e}")
        return set()


def save_progress(market: str, done_set: set) -> None:
    """เซฟรายชื่อ ticker ที่สแกนแล้ว"""
    os.makedirs(PROGRESS_DIR, exist_ok=True)
    path = _progress_path(market)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"done": sorted(done_set)}, f, ensure_ascii=False)
    except Exception as e:
        log.warning(f"เซฟ progress ล้มเหลว: {e}")


def clear_old_progress(keep_days: int = 3) -> None:
    """ลบไฟล์ progress เก่ากว่า keep_days วัน กันไฟล์สะสม"""
    if not os.path.isdir(PROGRESS_DIR):
        return
    import time
    now = time.time()
    for fn in os.listdir(PROGRESS_DIR):
        fp = os.path.join(PROGRESS_DIR, fn)
        try:
            if now - os.path.getmtime(fp) > keep_days * 86400:
                os.remove(fp)
        except Exception:
            pass


if __name__ == "__main__":
    # ทดสอบ
    save_progress("TEST", {"AAA", "BBB"})
    loaded = load_progress("TEST")
    print("โหลดได้:", loaded)
    assert loaded == {"AAA", "BBB"}
    loaded.add("CCC")
    save_progress("TEST", loaded)
    assert load_progress("TEST") == {"AAA", "BBB", "CCC"}
    print("✅ resume tracker ทำงานถูกต้อง")
    os.remove(_progress_path("TEST"))
