# วิธีตั้ง Stock Scanner บน GitHub Actions (ฟรี รัน 24/7 ไม่ต้องเปิดเครื่อง)

GitHub Actions รันบน cloud ของ GitHub ตามเวลาที่ตั้ง ไม่ต้องเปิดคอมทิ้งไว้
**ถ้าตั้ง repo เป็น public = ฟรีไม่จำกัดนาที** (token เก็บแยกใน Secrets ปลอดภัย)

## ขั้นตอน (ทำครั้งเดียว ~15 นาที)

### 1. สร้าง GitHub repo
1. ไปที่ github.com → New repository
2. ตั้งชื่อ เช่น `stock-scanner`
3. เลือก **Public** (เพื่อให้ฟรีไม่จำกัด — โค้ดไม่มีความลับ token อยู่ใน Secrets แยก)
4. กด Create

### 2. อัปโหลดไฟล์ทั้งหมดขึ้น repo
**วิธีง่าย (ผ่านเว็บ):** หน้า repo → Add file → Upload files → ลากไฟล์ทั้งหมด
(รวมโฟลเดอร์ `.github/workflows/scan.yml` ด้วย) → Commit

**หรือผ่าน git (ถ้าถนัด):**
```bash
cd stock_scanner
git init
git add .
git commit -m "initial stock scanner"
git branch -M main
git remote add origin https://github.com/<username>/stock-scanner.git
git push -u origin main
```

### 3. ตั้ง Secrets (เก็บ token ปลอดภัย ไม่โผล่ในโค้ด)
1. หน้า repo → **Settings** → Secrets and variables → **Actions**
2. กด **New repository secret** เพิ่ม 2 ตัว:

| Name | Secret (value) |
|---|---|
| `TELEGRAM_BOT_TOKEN` | token จาก BotFather |
| `TELEGRAM_CHAT_IDS` | chat id คั่นด้วย comma เช่น `123456789,-1001234567890` |

### 4. เปิดใช้ Actions
1. หน้า repo → แท็บ **Actions**
2. ถ้าเห็นข้อความให้ enable workflow → กด **I understand, enable**

### 5. ทดสอบรันทันที (ไม่ต้องรอ schedule)
1. แท็บ Actions → เลือก workflow "Stock Scanner"
2. กด **Run workflow** → เลือก branch main → Run
3. รอ 1-2 นาที (รอบทดสอบ) ดูผล log และเช็คว่า Telegram มีข้อความเข้า

## ตารางเวลาที่ตั้งไว้ (อัตโนมัติ)

workflow ใช้ UTC — แปลงเป็นเวลาไทยแล้ว:

| รอบ | เวลาไทย | UTC (ใน cron) | ตลาด |
|---|---|---|---|
| เช้า | 10:15 | 03:15 | SET |
| บ่าย | 16:00 | 09:00 | SET |
| ค่ำ | 20:45 | 13:45 | US |

> **DST สหรัฐฯ:** รอบ US ตั้งไว้ตรงช่วง EDT (มี.ค.-พ.ย.) ถ้าเข้าช่วง EST (พ.ย.-มี.ค.)
> ตลาดสหรัฐฯ จะเปิดช้าลง 1 ชม. → แก้ cron รอบ US เป็น `45 14 * * 1-5` ในไฟล์ scan.yml

## ข้อควรรู้

- **state (cache/progress)** ระบบจะ commit กลับเข้า repo อัตโนมัติหลังรันจบ
  เพื่อให้รอบถัดไปใช้ cache ได้ (เพราะ Actions ไม่เก็บไฟล์ข้ามรอบ)
- **schedule อาจดีเลย์** GitHub Actions cron บางครั้งช้า 5-15 นาทีช่วง peak — ปกติ ไม่ต้องกังวล
- **ปิดชั่วคราว:** Settings → Actions → Disable | หรือลบไฟล์ scan.yml
- ถ้าใช้ private repo แทน: ฟรี 2,000 นาที/เดือน — สแกนทั้งตลาดอาจไม่พอ แนะนำ public

## แก้ปัญหาที่พบบ่อย

- **ไม่มีข้อความเข้า Telegram** → เช็ค Secrets ว่าใส่ครบ/ถูก, ดู log ในแท็บ Actions
- **workflow ไม่รันตามเวลา** → เช็คว่า repo มี activity (repo ที่เงียบ 60 วัน GitHub จะ pause schedule อัตโนมัติ กด Run workflow เองสักครั้งจะ active ต่อ)
- **commit cache ล้มเหลว** → ตรวจว่า workflow มี `permissions: contents: write` (มีให้แล้วในไฟล์)
