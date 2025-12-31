import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import talib as ta
import yfinance as yf

# ----------------- Configuration -----------------
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

ASSETS = [
    "EURUSD=X", "AUDCHF=X", "GBPCHF=X", "EURCAD=X", "AUDCAD=X", 
    "USDCHF=X", "CADCHF=X", "AUDJPY=X", "CADJPY=X", "EURJPY=X", 
    "USDJPY=X", "GBPUSD=X", "EURGBP=X", "GBPJPY=X", "GBPAUD=X"
]

TIMEFRAME = 60  # 1-minute candles
TRADING_START = 10  # 10 AM GMT
TRADING_END = 22    # Adjusted to 10 PM GMT for better coverage

# Indicator settings
RSI_PERIOD = 10
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
SUPERTREND_PERIOD = 5
SUPERTREND_MULTIPLIER = 2

MIN_CONSOLIDATION_CANDLES = 20
BREAKOUT_LOOKBACK = 5  
# -------------------------------------------------

# Track sent signals to avoid spamming
last_sent_signals = {}

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Telegram error: {e}")

def fetch_candles(asset, count=100):
    try:
        ticker = yf.Ticker(asset)
        df = ticker.history(period="1d", interval="1m").tail(count)
        if df.empty:
            return pd.DataFrame()
        
        # Standardize columns for TA-Lib
        df = df.rename(columns={
            'Open': 'open', 'High': 'high', 'Low': 'low', 
            'Close': 'close', 'Volume': 'volume'
        })
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

    # Thresholds for slope detection
    if abs(high_slope) < 0.00005 and low_slope > 0.00005:
        return "Ascending"
    elif abs(low_slope) < 0.00005 and high_slope < -0.00005:
        return "Descending"
    elif high_slope < -0.00005 and low_slope > 0.00005:
        return "Symmetrical"
    return None

def check_breakout(df):
    last_close = df['close'].iloc[-1]
    # Look back at high/low before the current candle
    prev_high = df['high'].iloc[-(BREAKOUT_LOOKBACK+1):-1].max()
    prev_low = df['low'].iloc[-(BREAKOUT_LOOKBACK+1):-1].min()
    
    if last_close > prev_high:
        return "BUY"
    elif last_close < prev_low:
        return "SELL"
    return None

print("Bot started...")

while True:
    now = datetime.utcnow()
    if TRADING_START <= now.hour < TRADING_END:
        for asset in ASSETS:
            df = fetch_candles(asset, count=100)
            if df.empty or len(df) < 30:
                continue

            # Indicators
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

                    # Cooldown check: 15 minutes per asset
                    current_ts = time.time()
                    if confirm and (asset not in last_sent_signals or (current_ts - last_sent_signals[asset]) > 900):
                        msg = f"🚀 {signal} Alert!\nAsset: {asset}\nPattern: {triangle_type} Triangle\nPrice: {df['close'].iloc[-1]:.5f}\nTime: {now.strftime('%H:%M:%S')} UTC"
                        send_telegram_message(msg)
                        last_sent_signals[asset] = current_ts
                        print(f"Signal sent for {asset}")

    time.sleep(TIMEFRAME)
