"""
divergence.py
ตรวจจับ RSI Bullish Divergence — สัญญาณ "ทรงตัว low กำลังจะกลับตัว/เบรค"

หลักการ Bullish Divergence:
  ราคาทำ Lower Low (จุดต่ำใหม่ < จุดต่ำเดิม)
  แต่ RSI ทำ Higher Low (ไม่ลงตามราคา)
  => แรงขายอ่อนแรง มักเกิดก่อนกลับตัวขึ้น

วิธี: หา swing low 2 จุดล่าสุดของราคา แล้วเทียบ RSI ที่จุดเดียวกัน
"""

import numpy as np
import pandas as pd
from indicators import calc_rsi


def find_swing_lows(series: pd.Series, order: int = 5) -> list:
    """
    หา swing low: จุดที่เป็นต่ำสุดในกรอบ +/- order แท่ง
    ใช้ <= เพื่อจับก้นแบน (flat bottom) ได้ และ dedupe จุดที่ติดกัน
    คืน list ของ index ตำแหน่ง (integer position)
    """
    vals = series.values
    n = len(vals)
    raw = []
    for i in range(order, n - order):
        window = vals[i - order:i + order + 1]
        if vals[i] <= window.min() + 1e-9:  # เป็นต่ำสุดในกรอบ (เผื่อ flat)
            raw.append(i)
    # dedupe: จุดที่ติดกัน (ภายใน order แท่ง) ยุบเป็นจุดเดียว เก็บตัวที่ต่ำสุด
    if not raw:
        return []
    grouped = [[raw[0]]]
    for idx in raw[1:]:
        if idx - grouped[-1][-1] <= order:
            grouped[-1].append(idx)
        else:
            grouped.append([idx])
    lows = [min(g, key=lambda j: vals[j]) for g in grouped]
    return lows


def detect_bullish_divergence(df: pd.DataFrame,
                               rsi_period: int = 14,
                               swing_order: int = 5,
                               max_lookback: int = 60,
                               rsi_oversold_zone: float = 45) -> dict:
    """
    ตรวจ Bullish RSI Divergence จากข้อมูลราคา
    เงื่อนไข:
      - มี swing low อย่างน้อย 2 จุดในช่วง max_lookback ล่าสุด
      - ราคา swing low ล่าสุด < swing low ก่อนหน้า (lower low)
      - RSI ที่ swing low ล่าสุด > RSI ที่ swing low ก่อนหน้า (higher low)
      - RSI อยู่ในโซนค่อนข้างต่ำ (ยืนยันว่าเป็นการกลับตัวจาก low จริง)
    """
    if df is None or len(df) < max(max_lookback, rsi_period + 10):
        return {"has_divergence": False, "reason": "ข้อมูลไม่พอ"}

    df = df.copy()
    rsi = calc_rsi(df["Close"], rsi_period)
    df["RSI"] = rsi

    # โฟกัสช่วงล่าสุด
    recent = df.iloc[-max_lookback:].reset_index(drop=True)
    low_idx = find_swing_lows(recent["Low"], order=swing_order)

    if len(low_idx) < 2:
        return {"has_divergence": False, "reason": "swing low ไม่พอ 2 จุด"}

    # เอา 2 จุดล่าสุด
    i_prev, i_last = low_idx[-2], low_idx[-1]
    price_prev, price_last = recent["Low"].iloc[i_prev], recent["Low"].iloc[i_last]
    rsi_prev, rsi_last = recent["RSI"].iloc[i_prev], recent["RSI"].iloc[i_last]

    price_lower_low = price_last < price_prev
    rsi_higher_low = rsi_last > rsi_prev
    rsi_in_low_zone = rsi_last <= 55  # ยังไม่ overbought ขึ้นมาจาก low

    has_div = price_lower_low and rsi_higher_low and rsi_in_low_zone

    # ระยะห่างจาก swing low ล่าสุด — ถ้าใกล้ปัจจุบันยิ่งสด
    bars_since = len(recent) - 1 - i_last

    return {
        "has_divergence": bool(has_div),
        "price_prev_low": round(float(price_prev), 2),
        "price_last_low": round(float(price_last), 2),
        "rsi_prev_low": round(float(rsi_prev), 1),
        "rsi_last_low": round(float(rsi_last), 1),
        "bars_since_low": int(bars_since),
        "reason": (f"ราคา lower low ({price_prev:.2f}→{price_last:.2f}) "
                   f"แต่ RSI higher low ({rsi_prev:.1f}→{rsi_last:.1f})") if has_div else "ไม่เข้าเงื่อนไข",
    }


if __name__ == "__main__":
    # สร้างข้อมูลจำลองที่มี bullish divergence ชัดๆ
    n = 80
    rng = np.random.default_rng(3)
    price = np.zeros(n)
    price[0] = 100
    for i in range(1, n):
        price[i] = price[i-1] + rng.normal(-0.1, 0.8)
    # สร้าง 2 swing low: จุดแรกลึก, จุดสองลึกกว่า(ราคา) แต่ momentum ฟื้น
    price[30:36] = [95, 93, 91, 90, 92, 94]    # swing low แรก (ลึก, ราคาดิ่ง)
    price[55:61] = [91, 90, 89, 88, 91, 94]    # swing low สอง: ราคา lower low แต่ดิ่งช้ากว่า
    price[61:] = price[60] + np.cumsum(rng.uniform(0.2, 0.8, n-61))  # ฟื้นตัว

    df = pd.DataFrame({
        "Open": price, "High": price + 0.8, "Low": price - 0.8,
        "Close": price, "Volume": rng.integers(1_000_000, 2_000_000, n),
    })

    result = detect_bullish_divergence(df)
    print("=== ทดสอบ Bullish Divergence ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
