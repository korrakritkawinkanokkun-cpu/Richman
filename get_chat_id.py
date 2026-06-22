"""
get_chat_id.py
สคริปต์ช่วยหา CHAT_ID ของคุณ — รันครั้งเดียวตอนตั้งระบบครั้งแรก

วิธีใช้:
1. สร้างบอทกับ @BotFather ใน Telegram ก่อน จะได้ BOT_TOKEN
2. เปิดแชทกับบอทตัวเอง พิมพ์อะไรก็ได้ส่งไป 1 ข้อความ (เช่น "hi")
3. รันไฟล์นี้: python3 get_chat_id.py <BOT_TOKEN>
4. จะได้ CHAT_ID มาแสดง เอาไปใส่ใน config.py
"""

import sys
import requests


def main():
    if len(sys.argv) != 2:
        print("วิธีใช้: python3 get_chat_id.py <BOT_TOKEN>")
        sys.exit(1)

    token = sys.argv[1]
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    resp = requests.get(url, timeout=10)
    data = resp.json()

    if not data.get("ok"):
        print("เกิดข้อผิดพลาด:", data)
        sys.exit(1)

    results = data.get("result", [])
    if not results:
        print("ไม่พบข้อความเลย — ตรวจสอบว่าคุณส่งข้อความให้บอทตัวเองแล้วหรือยัง")
        sys.exit(1)

    seen = set()
    for r in results:
        msg = r.get("message", {})
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        name = chat.get("first_name", "") + " " + chat.get("last_name", "")
        if chat_id and chat_id not in seen:
            seen.add(chat_id)
            print(f"พบ CHAT_ID: {chat_id}  (ชื่อ: {name.strip()})")

    print("\nนำ CHAT_ID ด้านบนไปใส่ในไฟล์ config.py ที่ตัวแปร TELEGRAM_CHAT_ID")


if __name__ == "__main__":
    main()
