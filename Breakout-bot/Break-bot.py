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
    elif high_slope < -0.00005 and low_slope > 0.0
