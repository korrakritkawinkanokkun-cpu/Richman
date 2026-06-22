"""
telegram_notifier.py
ส่งข้อความแจ้งเตือนผ่าน Telegram Bot — รองรับหลาย chat ID (ส่วนตัว + กลุ่ม)

วิธีตั้งค่า:
1. เปิด Telegram หา @BotFather -> /newbot -> ได้ BOT_TOKEN
2. หา CHAT_ID: ส่งข้อความให้บอท (หรือเพิ่มบอทเข้ากลุ่ม+ปิด Group Privacy)
   แล้วรัน get_chat_id.py
3. ใส่ค่าใน config.py (TELEGRAM_CHAT_IDS รองรับหลายค่าเป็น list)
"""

import logging
import requests

log = logging.getLogger("telegram_notifier")

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram_message(bot_token: str, chat_id: str, text: str,
                          parse_mode: str = "Markdown",
                          disable_preview: bool = True) -> bool:
    """ส่งข้อความเดียวไป chat เดียว"""
    url = TELEGRAM_API_BASE.format(token=bot_token)
    payload = {
        "chat_id": chat_id, "text": text, "parse_mode": parse_mode,
        "disable_web_page_preview": disable_preview,
    }
    try:
        resp = requests.post(url, data=payload, timeout=10)
        if resp.status_code == 200:
            return True
        log.error(f"ส่ง Telegram (chat {chat_id}) ล้มเหลว: {resp.status_code} {resp.text}")
        return False
    except Exception as e:
        log.error(f"ส่ง Telegram (chat {chat_id}) error: {e}")
        return False


def _send_one_chat(bot_token: str, chat_id: str, text: str, chunk_size: int = 3500):
    """ส่งไป chat เดียว ตัดข้อความถ้ายาวเกิน"""
    if len(text) <= chunk_size:
        send_telegram_message(bot_token, chat_id, text)
        return
    parts = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    for idx, part in enumerate(parts, 1):
        header = f"(ส่วนที่ {idx}/{len(parts)})\n"
        send_telegram_message(bot_token, chat_id, header + part)


def send_to_all(bot_token: str, chat_ids, text: str, chunk_size: int = 3500) -> None:
    """
    ส่งข้อความไปทุก chat ใน chat_ids
    chat_ids: รับได้ทั้ง string เดี่ยว หรือ list ของ string (ส่วนตัว+กลุ่ม)
    """
    if isinstance(chat_ids, (str, int)):
        chat_ids = [chat_ids]
    for cid in chat_ids:
        cid = str(cid).strip()
        if cid and not cid.startswith("ใส่"):  # ข้าม placeholder ที่ยังไม่ตั้งค่า
            _send_one_chat(bot_token, cid, text, chunk_size)


def format_alert_message(market: str, results: list) -> str:
    """
    จัดรูปแบบผลสแกนเป็นข้อความ Telegram
    results: list ของ dict {ticker, setup, fundamental(optional), news(optional)}
    """
    if not results:
        return f"📊 *{market} Scan*\nรอบนี้ไม่มีตัวเข้าเกณฑ์ครับ"

    lines = [f"📊 *{market} Scan — พบ {len(results)} ตัวเข้าเกณฑ์*"]
    results_sorted = sorted(results, key=lambda r: r["setup"]["score"], reverse=True)

    for r in results_sorted:
        t = r["ticker"]
        s = r["setup"]
        tag = "⚡เบรคแล้ว" if s["already_broke"] else "🎯ตั้งท่าเบรค"
        block = [
            f"\n*{t}* {tag} (score {s['score']}/{s['max_score']})",
            f"ราคา: {s['close']} | RSI: {s['rsi']} | Vol: {s['vol_ratio']}x",
            f"แนวต้าน: {s['resistance']} | กรอบ: {s['range_width_pct']}%",
            f"เทคนิค: {', '.join(s['reasons'])}",
        ]
        # แนบ fundamental ถ้ามี
        if r.get("fundamental_line"):
            block.append(r["fundamental_line"])
        # แนบข่าวถ้ามี
        if r.get("news_block"):
            block.append(r["news_block"])
        lines.append("\n".join(block))

    lines.append("\n\n_ข้อมูลนี้เป็นผลจากการสแกนอัตโนมัติ ไม่ใช่คำแนะนำการลงทุน "
                 "ควรตรวจสอบเพิ่มก่อนตัดสินใจ_")
    return "\n".join(lines)


if __name__ == "__main__":
    fake = [{
        "ticker": "EGCO.BK",
        "setup": {"score": 4, "max_score": 5, "close": 105.5, "rsi": 52.3,
                  "vol_ratio": 1.8, "resistance": 107.0, "range_width_pct": 8.2,
                  "already_broke": False, "reasons": ["EMA20>EMA50", "Volume เพิ่ม"]},
        "fundamental_line": "💰 PE 12.50 | PBV 0.85 | ปันผล 5.2% | Cap 55.00B",
        "news_block": "📰 ข่าวล่าสุด:\n  • EGCO ลงทุนโรงไฟฟ้าใหม่ (SET News)",
    }]
    print(format_alert_message("SET", fake))
    print("\n--- test send_to_all กับ placeholder (ควรข้าม ไม่ error) ---")
    send_to_all("faketoken", ["ใส่ CHAT_ID ของคุณที่นี่"], "test")
    print("✅ ไม่ส่งไป placeholder, ไม่ crash")
