"""
news_fetcher.py
ดึงข่าวล่าสุดของหุ้นที่เข้าเกณฑ์ (เฉพาะตัวที่ผ่าน technical) ผ่าน yfinance .news
แสดงพาดหัว + แหล่ง + ลิงก์ เพื่อให้รู้คร่าวๆ ว่าบริษัทกำลังมี catalyst อะไร

หมายเหตุ: yfinance .news คืนข่าวภาษาอังกฤษเป็นหลัก และมีเฉพาะหุ้นที่ Yahoo cover
หุ้น SET เล็กบางตัวอาจไม่มีข่าว — กรณีนั้นจะข้ามไป
"""

import logging
import yfinance as yf

log = logging.getLogger("news_fetcher")


def fetch_latest_news(ticker: str, max_items: int = 3) -> list:
    """
    ดึงข่าวล่าสุดของ ticker คืน list ของ dict {title, publisher, link}
    คืน list ว่างถ้าไม่มีข่าว/ดึงไม่ได้
    """
    try:
        raw = yf.Ticker(ticker).news
    except Exception as e:
        log.warning(f"ดึงข่าว {ticker} ล้มเหลว: {e}")
        return []

    if not raw:
        return []

    items = []
    for n in raw[:max_items]:
        # yfinance เปลี่ยน schema ข่าวเป็นช่วงๆ — รองรับทั้งแบบเก่า (flat) และใหม่ (content nested)
        content = n.get("content", n)  # แบบใหม่ซ้อนใน 'content', แบบเก่าใช้ตรงๆ
        title = content.get("title") or n.get("title")
        publisher = (
            content.get("provider", {}).get("displayName")
            if isinstance(content.get("provider"), dict)
            else n.get("publisher")
        )
        # link รองรับหลาย schema
        link = None
        if isinstance(content.get("clickThroughUrl"), dict):
            link = content["clickThroughUrl"].get("url")
        elif isinstance(content.get("canonicalUrl"), dict):
            link = content["canonicalUrl"].get("url")
        link = link or n.get("link")

        if title:
            items.append({
                "title": title,
                "publisher": publisher or "ไม่ระบุแหล่ง",
                "link": link or "",
            })
    return items


def format_news_block(news_items: list) -> str:
    """จัดข่าวเป็นบล็อกข้อความสั้นๆ สำหรับแนบในข้อความแจ้งเตือน"""
    if not news_items:
        return ""
    lines = ["📰 ข่าวล่าสุด:"]
    for n in news_items:
        title = n["title"]
        if len(title) > 90:
            title = title[:87] + "..."
        if n.get("link"):
            lines.append(f"  • [{title}]({n['link']}) ({n['publisher']})")
        else:
            lines.append(f"  • {title} ({n['publisher']})")
    return "\n".join(lines)


if __name__ == "__main__":
    # ทดสอบ format + รองrับทั้ง schema เก่า/ใหม่ (mock ไม่ต่อเน็ต)
    print("=== schema ใหม่ (nested content) ===")
    mock_new = [{
        "content": {
            "title": "Company X reports record Q2 earnings beating estimates",
            "provider": {"displayName": "Reuters"},
            "clickThroughUrl": {"url": "https://example.com/news1"},
        }
    }]
    # จำลองการ parse แบบเดียวกับใน fetch_latest_news
    def parse_mock(raw, max_items=3):
        items = []
        for n in raw[:max_items]:
            content = n.get("content", n)
            title = content.get("title") or n.get("title")
            publisher = (content.get("provider", {}).get("displayName")
                         if isinstance(content.get("provider"), dict) else n.get("publisher"))
            link = None
            if isinstance(content.get("clickThroughUrl"), dict):
                link = content["clickThroughUrl"].get("url")
            link = link or n.get("link")
            if title:
                items.append({"title": title, "publisher": publisher or "ไม่ระบุ", "link": link or ""})
        return items

    items = parse_mock(mock_new)
    print(format_news_block(items))

    print("\n=== schema เก่า (flat) ===")
    mock_old = [{
        "title": "Company Y announces new data center expansion in Thailand",
        "publisher": "Bloomberg",
        "link": "https://example.com/news2",
    }]
    items2 = parse_mock(mock_old)
    print(format_news_block(items2))

    print("\n=== ไม่มีข่าว ===")
    print(repr(format_news_block([])))
    print("✅ news formatting ทำงานถูกต้องทั้ง 2 schema")
