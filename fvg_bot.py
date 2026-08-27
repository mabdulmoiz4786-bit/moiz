"""
Forex/Gold Trend + Fair Value Gap (FVG) Alert Bot
---------------------------------------------------
Fetches recent candles from Twelve Data, determines the current
trend (swing-based), scans the most recent candles for a Fair
Value Gap (ICT 3-candle imbalance) in the direction of that trend,
and emails an alert when one is found.

Designed to run on a schedule (e.g. every 15-30 min via GitHub
Actions cron, or a local cron job). It is stateless between runs
except for a small "already alerted" cache file so you don't get
the same alert repeated every run.
"""

import os
import json
import smtplib
import sys
from email.mime.text import MIMEText
from datetime import datetime, timezone

import requests

# --------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------

TWELVE_DATA_API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")
EMAIL_FROM = os.environ.get("ALERT_EMAIL_FROM", "")
EMAIL_APP_PASSWORD = os.environ.get("ALERT_EMAIL_APP_PASSWORD", "")
EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "abdulmoiz4718@gmail.com")

# Symbols to scan. Twelve Data format: "EUR/USD", "XAU/USD", etc.
SYMBOLS = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "USD/CHF",
    "AUD/USD",
    "USD/CAD",
    "NZD/USD",
    "XAU/USD",  # Gold
]

INTERVAL = "15min"      # candle timeframe to analyze
CANDLE_COUNT = 100       # how many candles to pull per symbol
SWING_LOOKBACK = 5       # bars on each side to confirm a swing high/low
FVG_SCAN_WINDOW = 5      # only look for a FVG within the last N candles (i.e. "fresh")

STATE_FILE = os.path.join(os.path.dirname(__file__), "alerted_state.json")


# --------------------------------------------------------------------
# DATA FETCHING
# --------------------------------------------------------------------

def fetch_candles(symbol: str):
    """Fetch OHLC candles from Twelve Data, oldest -> newest."""
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": INTERVAL,
        "outputsize": CANDLE_COUNT,
        "apikey": TWELVE_DATA_API_KEY,
        "order": "ASC",
    }
    resp = requests.get(url, params=params, timeout=30)
    data = resp.json()

    if "values" not in data:
        print(f"[{symbol}] API error or no data: {data}", file=sys.stderr)
        return []

    candles = []
    for row in data["values"]:
        candles.append({
            "time": row["datetime"],
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        })
    return candles


# --------------------------------------------------------------------
# TREND DETECTION (swing-based: higher highs/higher lows vs lower highs/lower lows)
# --------------------------------------------------------------------

def find_swings(candles, lookback=SWING_LOOKBACK):
    """Return lists of (index, price) for swing highs and swing lows."""
    highs, lows = [], []
    n = len(candles)
    for i in range(lookback, n - lookback):
        window = candles[i - lookback:i + lookback + 1]
        cur_high = candles[i]["high"]
        cur_low = candles[i]["low"]
        if cur_high == max(c["high"] for c in window):
            highs.append((i, cur_high))
        if cur_low == min(c["low"] for c in window):
            lows.append((i, cur_low))
    return highs, lows


def detect_trend(candles):
    """
    Returns 'uptrend', 'downtrend', or 'range' based on the last two
    confirmed swing highs and swing lows.
    """
    highs, lows = find_swings(candles)
    if len(highs) < 2 or len(lows) < 2:
        return "range"

    last_two_highs = highs[-2:]
    last_two_lows = lows[-2:]

    higher_high = last_two_highs[1][1] > last_two_highs[0][1]
    higher_low = last_two_lows[1][1] > last_two_lows[0][1]
    lower_high = last_two_highs[1][1] < last_two_highs[0][1]
    lower_low = last_two_lows[1][1] < last_two_lows[0][1]

    if higher_high and higher_low:
        return "uptrend"
    if lower_high and lower_low:
        return "downtrend"
    return "range"


# --------------------------------------------------------------------
# FVG (FAIR VALUE GAP) DETECTION
# --------------------------------------------------------------------

def find_fvgs(candles, window=FVG_SCAN_WINDOW):
    """
    Classic 3-candle FVG:
      Bullish FVG: low of candle[i+2] > high of candle[i]  (gap left below price)
      Bearish FVG: high of candle[i+2] < low of candle[i]  (gap left above price)
    Only returns FVGs whose middle candle falls within the last `window`
    candles (i.e. recently formed / still "fresh").
    """
    fvgs = []
    n = len(candles)
    start = max(2, n - window - 2)

    for i in range(start, n - 2):
        c1, c3 = candles[i], candles[i + 2]

        if c3["low"] > c1["high"]:
            fvgs.append({
                "type": "bullish",
                "top": c3["low"],
                "bottom": c1["high"],
                "time": candles[i + 1]["time"],
            })
        elif c3["high"] < c1["low"]:
            fvgs.append({
                "type": "bearish",
                "top": c1["low"],
                "bottom": c3["high"],
                "time": candles[i + 1]["time"],
            })

    return fvgs


# --------------------------------------------------------------------
# STATE (avoid duplicate alerts for the same FVG)
# --------------------------------------------------------------------

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


# --------------------------------------------------------------------
# EMAIL
# --------------------------------------------------------------------

def send_email(subject: str, body: str):
    if not EMAIL_FROM or not EMAIL_APP_PASSWORD:
        print("Email credentials not set — skipping send. Message was:")
        print(subject)
        print(body)
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_APP_PASSWORD)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())

    print(f"Email sent: {subject}")


# --------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------

def main():
    if not TWELVE_DATA_API_KEY:
        print("TWELVE_DATA_API_KEY not set. Exiting.", file=sys.stderr)
        sys.exit(1)

    state = load_state()
    alerts_sent = []

    for symbol in SYMBOLS:
        candles = fetch_candles(symbol)
        if len(candles) < (SWING_LOOKBACK * 2 + 2):
            continue

        trend = detect_trend(candles)
        if trend == "range":
            continue  # only alert with the trend

        fvgs = find_fvgs(candles)

        # Only take FVGs that align with the trend direction:
        # uptrend -> look for bullish FVG (potential long entry on retrace)
        # downtrend -> look for bearish FVG (potential short entry on retrace)
        wanted_type = "bullish" if trend == "uptrend" else "bearish"
        aligned = [f for f in fvgs if f["type"] == wanted_type]

        for fvg in aligned:
            key = f"{symbol}_{fvg['time']}_{fvg['type']}"
            if state.get(key):
                continue  # already alerted this one

            direction = "LONG (uptrend + bullish FVG)" if trend == "uptrend" else "SHORT (downtrend + bearish FVG)"
            subject = f"[FVG Alert] {symbol} — {direction}"
            body = (
                f"Symbol: {symbol}\n"
                f"Trend: {trend}\n"
                f"FVG type: {fvg['type']}\n"
                f"FVG zone: {fvg['bottom']:.5f} - {fvg['top']:.5f}\n"
                f"FVG candle time: {fvg['time']}\n"
                f"Detected at: {datetime.now(timezone.utc).isoformat()}\n\n"
                f"This is an automated technical alert, not financial advice. "
                f"Confirm on your own chart before taking any trade."
            )
            send_email(subject, body)
            state[key] = True
            alerts_sent.append(key)

    save_state(state)
    print(f"Run complete. {len(alerts_sent)} new alert(s) sent.")


if __name__ == "__main__":
    main()
