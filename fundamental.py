"""
fundamental.py
ดึงข้อมูลพื้นฐาน (Value/Fundamental) เสริมเฉพาะหุ้นที่ผ่านชั้น technical แล้ว
ใช้ yfinance .info / .fast_info — ดึงเฉพาะตัวที่เข้าเกณฑ์ จึงไม่หนักระบบ

หมายเหตุ: yfinance .info เป็น unofficial บางฟิลด์อาจว่าง/ขาดเป็นบางตัว
จึงใช้ .get() กันพังทุกฟิลด์ และแสดงเท่าที่มี
"""

import logging
import yfinance as yf

log = logging.getLogger("fundamental")


def fetch_fundamentals(ticker: str) -> dict:
    """
    ดึงข้อมูลพื้นฐานของหุ้นตัวเดียว คืน dict (ฟิลด์ไหนไม่มีจะเป็น None)
    ใช้ try/except กันพัง เพราะ .info ล่มบางตัวได้
    """
    result = {
        "pe": None, "forward_pe": None, "pbv": None,
        "roe": None, "profit_margin": None,
        "revenue_growth": None, "earnings_growth": None,
        "market_cap": None, "dividend_yield": None,
        "sector": None, "industry": None,
    }
    try:
        info = yf.Ticker(ticker).info
    except Exception as e:
        log.warning(f"ดึง fundamental {ticker} ล้มเหลว: {e}")
        return result

    if not info or not isinstance(info, dict):
        return result

    result["pe"] = info.get("trailingPE")
    result["forward_pe"] = info.get("forwardPE")
    result["pbv"] = info.get("priceToBook")
    result["roe"] = info.get("returnOnEquity")
    result["profit_margin"] = info.get("profitMargins")
    result["revenue_growth"] = info.get("revenueGrowth")
    result["earnings_growth"] = info.get("earningsGrowth")
    result["market_cap"] = info.get("marketCap")
    result["dividend_yield"] = info.get("dividendYield")
    result["sector"] = info.get("sector")
    result["industry"] = info.get("industry")
    return result


def _fmt_pct(v):
    """แปลงสัดส่วน (0.15) เป็น % string (15.0%) คืน '-' ถ้า None"""
    if v is None:
        return "-"
    try:
        return f"{v * 100:.1f}%"
    except Exception:
        return "-"


def _fmt_dividend(v):
    """
    dividend yield จาก yfinance มาไม่สม่ำเสมอ:
    บางตัวเป็นสัดส่วน (0.058 = 5.8%), บางตัวเป็น % แล้ว (5.8)
    ตรวจขนาด: ถ้า >= 1 ถือว่าเป็น % อยู่แล้ว, ถ้า < 1 ค่อยคูณ 100
    """
    if v is None:
        return "-"
    try:
        pct = v if v >= 1 else v * 100
        return f"{pct:.1f}%"
    except Exception:
        return "-"


def _fmt_num(v, suffix=""):
    if v is None:
        return "-"
    try:
        return f"{v:.2f}{suffix}"
    except Exception:
        return "-"


def _fmt_mktcap(v):
    if v is None:
        return "-"
    try:
        if v >= 1e12:
            return f"{v/1e12:.2f}T"
        if v >= 1e9:
            return f"{v/1e9:.2f}B"
        if v >= 1e6:
            return f"{v/1e6:.2f}M"
        return str(v)
    except Exception:
        return "-"


def format_fundamental_line(fund: dict) -> str:
    """จัดข้อมูลพื้นฐานเป็นบรรทัดสั้นๆ สำหรับแนบในข้อความแจ้งเตือน"""
    parts = []
    if fund.get("pe") is not None:
        parts.append(f"PE {_fmt_num(fund['pe'])}")
    if fund.get("pbv") is not None:
        parts.append(f"PBV {_fmt_num(fund['pbv'])}")
    if fund.get("revenue_growth") is not None:
        parts.append(f"รายได้โต {_fmt_pct(fund['revenue_growth'])}")
    if fund.get("roe") is not None:
        parts.append(f"ROE {_fmt_pct(fund['roe'])}")
    if fund.get("dividend_yield") is not None:
        parts.append(f"ปันผล {_fmt_dividend(fund['dividend_yield'])}")
    mc = _fmt_mktcap(fund.get("market_cap"))
    if mc != "-":
        parts.append(f"Cap {mc}")

    if not parts:
        return "ข้อมูลพื้นฐาน: ไม่มีข้อมูล"
    return "💰 " + " | ".join(parts)


if __name__ == "__main__":
    # ทดสอบ format ด้วยข้อมูลจำลอง (ไม่ต่อเน็ต)
    sample = {
        "pe": 18.5, "forward_pe": 16.2, "pbv": 2.3, "roe": 0.215,
        "profit_margin": 0.18, "revenue_growth": 0.12, "earnings_growth": 0.25,
        "market_cap": 3.2e9, "dividend_yield": 0.034,
        "sector": "Technology", "industry": "Software",
    }
    print(format_fundamental_line(sample))

    # ทดสอบกรณีข้อมูลขาด
    empty = {k: None for k in sample}
    print(format_fundamental_line(empty))

    partial = {k: None for k in sample}
    partial["pe"] = 25.0
    partial["dividend_yield"] = 0.05
    print(format_fundamental_line(partial))
    print("✅ format fundamental ทำงานถูกต้อง")
