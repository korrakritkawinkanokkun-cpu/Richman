# Stock Scanner — SET + US Market Multi-Layer Alert

ระบบสแกนหุ้น **ทั้งตลาด SET (SET+mai) และ US (Nasdaq + NYSE + AMEX)**
วิเคราะห์ 3 ชั้น: **เทคนิค → พื้นฐาน → ข่าว** แล้วแจ้งเตือนผ่าน Telegram อัตโนมัติ

## Pipeline การทำงาน

```
Stage 0: โหลด universe ทั้งตลาด (มี cache รายวัน)
   ↓
Stage 1: Liquidity filter — กรองหุ้นเล็ก/ไม่มีสภาพคล่องออก (เบา เร็ว)
   ↓
Stage 2: Technical scan — EMA/RSI/MACD/breakout (เฉพาะตัวที่ผ่าน Stage 1)
   ↓
Stage 3: เสริม Fundamental (PE/PBV/กำไรโต) + News (ข่าวล่าสุด)
         เฉพาะตัวที่ผ่าน technical เท่านั้น (ไม่หนักระบบ)
   ↓
Stage 4: ส่ง Telegram (รองรับหลาย chat + กลุ่ม)
```

## โครงสร้างไฟล์

| ไฟล์ | หน้าที่ |
|---|---|
| `config.py` | ตั้งค่าทั้งหมด — แก้ที่นี่เป็นหลัก |
| `main_scanner.py` | สคริปต์หลัก (ตัวที่ตั้ง cron เรียก) |
| `data_fetcher.py` | ดึง universe + liquidity filter + ราคาประวัติศาสตร์ |
| `indicators.py` | คำนวณ indicator + ตัดสินเกณฑ์ breakout |
| `fundamental.py` | ดึง PE/PBV/ROE/กำไรโต (Stage 3) |
| `news_fetcher.py` | ดึงข่าวล่าสุด (Stage 3) |
| `telegram_notifier.py` | ส่งข้อความ (หลาย chat/กลุ่ม) |
| `universe_cache.py` | cache รายชื่อหุ้นรายวัน |
| `resume_tracker.py` | จำว่าสแกนถึงไหนแล้ว กัน interrupt |
| `get_chat_id.py` | หา Telegram Chat ID (รันครั้งเดียวตอนติดตั้ง) |

## ติดตั้งครั้งแรก

```bash
pip install -r requirements.txt
```

### Telegram Bot
1. `@BotFather` → `/newbot` → ได้ **BOT_TOKEN**
2. ส่งข้อความหาบอท (หรือเพิ่มเข้ากลุ่ม — ดูด้านล่าง)
3. `python get_chat_id.py <BOT_TOKEN>` → ได้ **CHAT_ID**
4. ใส่ใน `config.py`:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_IDS = ["123456789"]` (ใส่หลายค่าได้)

### ส่งเข้ากลุ่ม (option)
1. เพิ่มบอทเข้ากลุ่ม
2. `@BotFather` → `/mybots` → เลือกบอท → Bot Settings → Group Privacy → **Turn off**
3. พิมพ์ข้อความในกลุ่ม 1 ที แล้วรัน `get_chat_id.py` → ได้ chat ID กลุ่ม (เลขติดลบ)
4. ใส่ใน `TELEGRAM_CHAT_IDS` เช่น `["123456789", "-1001234567890"]`

### ทดสอบรัน
```bash
python main_scanner.py --market SET
python main_scanner.py --market US
```

## ตั้ง Cron (3 รอบ/วัน)

```
# SET: 10:15, 16:00 จันทร์-ศุกร์ (เวลาไทย)
15 10 * * 1-5 cd /path/to/stock_scanner && python3 main_scanner.py --market SET >> cron.log 2>&1
0 16 * * 1-5 cd /path/to/stock_scanner && python3 main_scanner.py --market SET >> cron.log 2>&1
# US: 20:45 จันทร์-ศุกร์ (เวลาไทย, ช่วง EDT)
45 20 * * 1-5 cd /path/to/stock_scanner && python3 main_scanner.py --market US >> cron.log 2>&1
```
DST: ตลาดสหรัฐฯ = ไทย 20:30 (EDT มี.ค.-พ.ย.) หรือ 21:30 (EST พ.ย.-มี.ค.)

## เกณฑ์ตัดสิน (score เต็ม 5)
1. EMA20 > EMA50 หรือกำลังตัดขึ้น
2. RSI(14) โซน 45-62
3. Volume ≥ 1.3x ค่าเฉลี่ย 20 วัน
4. MACD histogram ตัดขึ้น
5. Sideways แคบ + ชนแนวต้าน

**Pattern ที่จับได้ (อย่างน้อย 1 อย่าง):**
- 🎯 ตั้งท่าเบรค (sideways แคบ ชนแนวต้าน)
- ⚡ เบรคแล้ว (ทะลุแนวต้าน + volume ยืนยัน)
- 🔄 RSI Bullish Divergence (ราคาทำ lower low แต่ RSI ทำ higher low = ทรง low กำลังกลับตัว)

แจ้งเตือนเฉพาะ **score ≥ 3 และมีอย่างน้อย 1 pattern** (ปรับที่ `config.py`)
เปิด/ปิด divergence ที่ `ENABLE_RSI_DIVERGENCE`

## เปิด/ปิด feature (ใน config.py)
- `ENABLE_FUNDAMENTAL` — ชั้นพื้นฐาน
- `ENABLE_NEWS` — ชั้นข่าว
- `ENABLE_UNIVERSE_CACHE` — cache รายชื่อหุ้นรายวัน
- `ENABLE_RESUME` — กัน interrupt (ข้ามตัวที่สแกนแล้ววันนี้)

## ข้อควรระวัง
- universe ใหญ่มาก (US ~7,000 + SET ~800) — Stage 1 อาจใช้ 30-60 นาที
- yfinance unofficial — ถ้าพังกะทันหัน `pip install --upgrade yfinance`
- `.info` (fundamental) บางตัวข้อมูลขาดได้ ระบบแสดงเท่าที่มี
- ผลลัพธ์เป็นข้อมูลประกอบการตัดสินใจ ไม่ใช่คำแนะนำการลงทุน

## แผนพัฒนาต่อ (ถ้าต้องการ)
- จัด ranking รวม technical+fundamental เป็นคะแนนเดียว
- เก็บประวัติสัญญาณลงไฟล์/ฐานข้อมูล ดู backtest ย้อนหลัง
- กรองข่าวเฉพาะภาษาไทยสำหรับ SET
