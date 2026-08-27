# Forex/Gold Trend + FVG Alert Bot

Scans major forex pairs + Gold (XAU/USD) on a schedule. Detects the
current trend (swing-based) and looks for a fresh Fair Value Gap (FVG)
in that trend's direction. Emails you when one appears.

## What it checks
- **Trend**: uptrend (higher highs + higher lows) or downtrend (lower
  highs + lower lows) over the last two confirmed swings.
- **FVG**: classic 3-candle imbalance (ICT concept) — only alerts on
  FVGs that match the trend direction (bullish FVG in an uptrend,
  bearish FVG in a downtrend), and only if formed in the last few candles.

This is pure price-math (no AI in the loop) so it runs fast, cheap,
and consistently on a schedule.

## Setup (GitHub Actions — free, runs 24/7 without your PC on)

1. **Create a GitHub account** (free) if you don't have one, and create
   a new **public** repository (public repos get unlimited free Actions
   minutes; private repos get 2,000 free minutes/month, which is plenty
   at a 15-min interval too — about 2,880 runs/month at a few seconds each).

2. **Upload these files** to the repo, keeping the folder structure:
   - `fvg_bot.py`
   - `requirements.txt`
   - `.github/workflows/fvg-bot.yml`

3. **Get a Gmail App Password** (needed because Gmail blocks plain
   password login for scripts):
   - Go to your Google Account → Security → 2-Step Verification (turn on
     if not already on) → App Passwords → generate one for "Mail".
   - Copy the 16-character password it gives you.

4. **Add secrets to your GitHub repo**:
   - Repo → Settings → Secrets and variables → Actions → New repository secret.
   - Add these four:
     - `TWELVE_DATA_API_KEY` → your Twelve Data key
     - `ALERT_EMAIL_FROM` → the Gmail address you'll send *from*
     - `ALERT_EMAIL_APP_PASSWORD` → the app password from step 3
     - `ALERT_EMAIL_TO` → abdulmoiz4718@gmail.com

5. **Done.** The workflow runs automatically every 15 minutes. You can
   also trigger it manually anytime from the repo's "Actions" tab →
   "FVG Alert Bot" → "Run workflow".

## Adjusting behavior

Edit the top of `fvg_bot.py`:
- `SYMBOLS` — add/remove pairs
- `INTERVAL` — candle timeframe (e.g. "5min", "15min", "1h", "4h")
- `SWING_LOOKBACK` — how many bars confirm a swing point (bigger = fewer,
  more significant swings)
- `FVG_SCAN_WINDOW` — how recent an FVG must be to count as "fresh"

## Running locally instead (needs your PC on)

```bash
pip install -r requirements.txt
export TWELVE_DATA_API_KEY="your_key"
export ALERT_EMAIL_FROM="you@gmail.com"
export ALERT_EMAIL_APP_PASSWORD="your_app_password"
export ALERT_EMAIL_TO="abdulmoiz4718@gmail.com"
python fvg_bot.py
```

Then schedule it with cron (Linux/Mac) or Task Scheduler (Windows) to
run every 15 minutes.

## Important note

This tool flags a **technical pattern**, not a trade recommendation.
Always confirm on your own chart and manage risk — it's not financial
advice.
