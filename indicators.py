"""
indicators.py
คำนวณ technical indicators และตัดสินเกณฑ์ "น่าเข้า / ตั้งท่าจะเบรค"
ใช้กับ DataFrame ที่มีคอลัมน์: Open, High, Low, Close, Volume (จาก yfinance)
"""

import pandas as pd
import numpy as np


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    # Wilder smoothing แบบง่าย (rolling mean) — เพียงพอสำหรับ screening
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def calc_macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = calc_ema(series, fast)
    ema_slow = calc_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calc_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=period).mean()


def detect_setup(df: pd.DataFrame, lookback_range: int = 15) -> dict:
    """
    ตรวจสอบเกณฑ์ 'น่าเข้า / ตั้งท่าจะเบรค' จาก DataFrame ราคา
    คืนค่า dict สรุปผล + คะแนนรวม (score 0-5)
    """
    if df is None or len(df) < 60:
        return {"valid": False, "reason": "ข้อมูลไม่พอคำนวณ (ต้องการ >= 60 แท่ง)"}

    df = df.copy()
    df["EMA20"] = calc_ema(df["Close"], 20)
    df["EMA50"] = calc_ema(df["Close"], 50)
    df["RSI14"] = calc_rsi(df["Close"], 14)
    macd_line, signal_line, hist = calc_macd(df["Close"])
    df["MACD"] = macd_line
    df["MACD_SIGNAL"] = signal_line
    df["MACD_HIST"] = hist
    df["VOL_AVG20"] = df["Volume"].rolling(20).mean()
    df["ATR14"] = calc_atr(df, 14)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    score = 0
    reasons = []

    # 1) EMA alignment (trend ขึ้น หรือกำลังจะตัดขึ้น)
    ema_bullish = last["EMA20"] > last["EMA50"]
    ema_crossing_up = (prev["EMA20"] <= prev["EMA50"]) and (last["EMA20"] > last["EMA50"])
    if ema_bullish:
        score += 1
        reasons.append("EMA20>EMA50 (trend ขึ้น)")
    if ema_crossing_up:
        score += 1
        reasons.append("EMA20 ตัดขึ้น EMA50 (golden cross ใหม่)")

    # 2) RSI โซนฟื้นตัว ไม่ overbought
    if 45 <= last["RSI14"] <= 62:
        score += 1
        reasons.append(f"RSI={last['RSI14']:.1f} (โซนฟื้นตัว)")

    # 3) Volume เพิ่มกว่าค่าเฉลี่ย
    vol_ratio = last["Volume"] / last["VOL_AVG20"] if last["VOL_AVG20"] else 0
    if vol_ratio >= 1.3:
        score += 1
        reasons.append(f"Volume {vol_ratio:.1f}x ของค่าเฉลี่ย 20 วัน")

    # 4) MACD histogram กำลังตัดขึ้นหรือใกล้ตัดขึ้น
    macd_turning_up = (last["MACD_HIST"] > prev["MACD_HIST"]) and (last["MACD_HIST"] > -abs(last["MACD_HIST"]) * 0.1 if last["MACD_HIST"] < 0 else True)
    macd_cross_soon = last["MACD_HIST"] < 0 and last["MACD_HIST"] > prev["MACD_HIST"] and abs(last["MACD_HIST"]) < df["MACD_HIST"].abs().rolling(20).mean().iloc[-1]
    if last["MACD_HIST"] > prev["MACD_HIST"] and last["MACD_HIST"] > prev["MACD_HIST"] * 0.5:
        score += 1
        reasons.append("MACD histogram กำลังตัดขึ้น")

    # 5) Sideways แล้วชนแนวต้าน (breakout setup)
    recent = df.iloc[-lookback_range:]
    resistance = recent["High"].iloc[:-1].max()  # แนวต้านจาก N วันก่อนหน้า (ไม่รวมวันนี้)
    range_width_pct = (recent["High"].max() - recent["Low"].min()) / recent["Close"].mean() * 100
    near_resistance = last["Close"] >= resistance * 0.985  # อยู่ใกล้/ชนแนวต้านภายใน 1.5%
    is_tight_range = range_width_pct < 12  # กรอบแคบ <12% ใน N วัน

    breakout_setup = near_resistance and is_tight_range
    if breakout_setup:
        score += 1
        reasons.append(f"ราคาชนแนวต้าน {resistance:.2f} หลัง sideways แคบ ({range_width_pct:.1f}%)")

    already_broke = last["Close"] > resistance and last["Volume"] > last["VOL_AVG20"]
    if already_broke:
        reasons.append("⚡ เบรคแนวต้านแล้ว พร้อม volume ยืนยัน")

    return {
        "valid": True,
        "score": score,
        "max_score": 5,
        "close": round(float(last["Close"]), 2),
        "ema20": round(float(last["EMA20"]), 2),
        "ema50": round(float(last["EMA50"]), 2),
        "rsi": round(float(last["RSI14"]), 1),
        "macd_hist": round(float(last["MACD_HIST"]), 4),
        "vol_ratio": round(float(vol_ratio), 2),
        "resistance": round(float(resistance), 2),
        "range_width_pct": round(float(range_width_pct), 1),
        "breakout_setup": bool(breakout_setup),
        "already_broke": bool(already_broke),
        "reasons": reasons,
    }


def is_actionable(setup: dict, min_score: int = 3) -> bool:
    """ตัดสินว่า setup นี้ 'น่าสนใจพอจะแจ้งเตือน' หรือไม่"""
    if not setup.get("valid"):
        return False
    return setup["score"] >= min_score and (setup["breakout_setup"] or setup["already_broke"])


if __name__ == "__main__":
    # ทดสอบด้วยข้อมูลสมมติ (random walk + breakout pattern ปลอม) เพื่อเช็ค logic ไม่ error
    import numpy as np
    rng = np.random.default_rng(42)
    n = 100
    base = 100 + np.cumsum(rng.normal(0, 0.5, n))
    base[-15:] = base[-15] + np.linspace(0, 3, 15)  # ดันราคาขึ้นช่วงท้าย จำลอง breakout
    df_test = pd.DataFrame({
        "Open": base,
        "High": base + rng.uniform(0.5, 1.5, n),
        "Low": base - rng.uniform(0.5, 1.5, n),
        "Close": base,
        "Volume": rng.integers(1_000_000, 2_000_000, n),
    })
    df_test.loc[df_test.index[-1], "Volume"] = 5_000_000  # volume spike วันล่าสุด

    result = detect_setup(df_test)
    print("ผลทดสอบ detect_setup():")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print("\nactionable:", is_actionable(result))
