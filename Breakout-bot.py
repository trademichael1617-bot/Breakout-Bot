import os
import time
import threading
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import talib as ta
import yfinance as yf
from flask import Flask

# ----------------- Configuration (Render Env Vars) -----------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Safety check to ensure the bot doesn't start without credentials
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("CRITICAL ERROR: Telegram credentials not found in environment variables!")
    exit(1)
ASSETS = [
    "EURUSD=X", "AUDCHF=X", "GBPCHF=X", "EURCAD=X", "AUDCAD=X", 
    "USDCHF=X", "CADCHF=X", "AUDJPY=X", "CADJPY=X", "EURJPY=X", 
    "USDJPY=X", "GBPUSD=X", "EURGBP=X", "GBPJPY=X", "GBPAUD=X"
]

TIMEFRAME = 60  
TRADING_START = 10  
TRADING_END = 22    

# Indicator settings
RSI_PERIOD = 10
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
SUPERTREND_PERIOD = 5
SUPERTREND_MULTIPLIER = 2

MIN_CONSOLIDATION_CANDLES = 20
BREAKOUT_LOOKBACK = 5  

last_sent_signals = {}

# ----------------- Web Server for Render -----------------
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running", 200

def run_web_server():
    app.run(host='0.0.0.0', port=10000)

# ----------------- Setup Session -----------------
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Origin': 'https://finance.yahoo.com',
    'Referer': 'https://finance.yahoo.com'
})

# ----------------- Helper Functions -----------------

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def fetch_candles(asset, count=100):
    try:
        ticker = yf.Ticker(asset, session=session)
        df = ticker.history(period="2d", interval="1m").tail(count)
        if df.empty:
            return pd.DataFrame()
        df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
        return df
    except Exception as e:
        print(f"Error fetching {asset}: {e}")
        return pd.DataFrame()

def supertrend(df, period=SUPERTREND_PERIOD, multiplier=SUPERTREND_MULTIPLIER):
    hl2 = (df['high'] + df['low']) / 2
    atr = ta.ATR(df['high'], df['low'], df['close'], timeperiod=period)
    upperband = hl2 + multiplier * atr
    lowerband = hl2 - multiplier * atr
    direction = np.zeros(len(df))
    curr_dir = 1
    for i in range(1, len(df)):
        if df['close'].iloc[i] > upperband.iloc[i-1]:
            curr_dir = 1
        elif df['close'].iloc[i] < lowerband.iloc[i-1]:
            curr_dir = -1
        direction[i] = curr_dir
    return pd.Series(direction, index=df.index)

def detect_triangle_type(df):
    recent = df.tail(MIN_CONSOLIDATION_CANDLES)
    highs = recent['high'].values
    lows = recent['low'].values
    x = np.arange(len(highs))
    high_slope, _ = np.polyfit(x, highs, 1)
    low_slope, _ = np.polyfit(x, lows, 1)
    if abs(high_slope) < 0.00005 and low_slope > 0.00005:
        return "Ascending"
    elif abs(low_slope) < 0.00005 and high_slope < -0.00005:
        return "Descending"
    elif high_slope < -0.00005 and low_slope > 0.00005:
        return "Symmetrical"
    return None

def check_breakout(df):
    last_close = df['close'].iloc[-1]
    prev_high = df['high'].iloc[-(BREAKOUT_LOOKBACK+1):-1].max()
    prev_low = df['low'].iloc[-(BREAKOUT_LOOKBACK+1):-1].min()
    if last_close > prev_high:
        return "BUY"
    elif last_close < prev_low:
        return "SELL"
    return None

# ----------------- Main Loop -----------------

def main_bot_logic():
    print("Bot logic started...")
    while True:
        now = datetime.now(timezone.utc)
        
        if TRADING_START <= now.hour < TRADING_END:
            for asset in ASSETS:
                df = fetch_candles(asset, count=100)
                
                # Small delay between assets to prevent Yahoo block
                time.sleep(2) 
                
                if df.empty or len(df) < 30:
                    continue

                df['rsi'] = ta.RSI(df['close'], RSI_PERIOD)
                macd, macd_signal, _ = ta.MACD(df['close'], MACD_FAST, MACD_SLOW, MACD_SIGNAL)
                df['macd'] = macd
                df['macd_signal'] = macd_signal
                df['supertrend'] = supertrend(df)

                triangle_type = detect_triangle_type(df)
                if triangle_type:
                    signal = check_breakout(df)
                    if signal:
                        last_rsi = df['rsi'].iloc[-1]
                        last_macd = df['macd'].iloc[-1]
                        last_macd_signal = df['macd_signal'].iloc[-1]
                        last_st = df['supertrend'].iloc[-1]

                        confirm = False
                        if signal == "BUY" and last_rsi > 50 and last_macd > last_macd_signal and last_st == 1:
                            confirm = True
                        elif signal == "SELL" and last_rsi < 50 and last_macd < last_macd_signal and last_st == -1:
                            confirm = True

                        current_ts = time.time()
                        if confirm and (asset not in last_sent_signals or (current_ts - last_sent_signals[asset]) > 900):
                            msg = f"🚀 *{signal} Alert!*\nAsset: `{asset}`\nPattern: {triangle_type} Triangle\nPrice: {df['close'].iloc[-1]:.5f}\nTime: {now.strftime('%H:%M:%S')} UTC"
                            send_telegram_message(msg)
                            last_sent_signals[asset] = current_ts
                            print(f"Signal sent for {asset}")

        time.sleep(TIMEFRAME)

if __name__ == "__main__":
    # 1. Start Web Server
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # 2. Startup Notification
    startup_msg = (
        "🤖 *Breakout Bot is Live!*\n"
        f"Time: `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC`\n"
        f"Monitoring `{len(ASSETS)}` pairs."
    )
    send_telegram_message(startup_msg)
    
    # 3. Start Logic
    main_bot_logic()
