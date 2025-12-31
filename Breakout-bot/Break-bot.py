import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import talib as ta

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
TRADING_END = 12    # 12 PM GMT

# Indicator settings
RSI_PERIOD = 10
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
SUPERTREND_PERIOD = 5
SUPERTREND_MULTIPLIER = 2

# Minimum candles for triangle consolidation
MIN_CONSOLIDATION_CANDLES = 20

# -------------------------------------------------

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=payload)

# Placeholder: Fetch candle data from Pocket Option API / Web automation
def fetch_candles(asset, count=100):
    """
    Should return a pandas DataFrame with columns: 
    ['time','open','high','low','close','volume']
    """
    # Replace this with actual API/websocket fetch
    return pd.DataFrame()

# Calculate SuperTrend
def supertrend(df, period=SUPERTREND_PERIOD, multiplier=SUPERTREND_MULTIPLIER):
    hl2 = (df['high'] + df['low']) / 2
    atr = ta.ATR(df['high'], df['low'], df['close'], timeperiod=period)
    final_upperband = hl2 + (multiplier * atr)
    final_lowerband = hl2 - (multiplier * atr)
    supertrend = pd.Series(np.zeros(len(df)))
    direction = 1  # 1 for uptrend, -1 for downtrend

    for i in range(1, len(df)):
        if df['close'].iloc[i] > final_upperband.iloc[i-1]:
            direction = 1
        elif df['close'].iloc[i] < final_lowerband.iloc[i-1]:
            direction = -1
        supertrend.iloc[i] = direction

    return supertrend

# Detect triangle consolidation
def detect_triangle(df):
    recent = df[-MIN_CONSOLIDATION_CANDLES:]
    highs = recent['high'].values
    lows = recent['low'].values
    if len(highs) < 2:
        return False
    # Check convergence: highs decreasing, lows increasing
    high_slope = np.polyfit(range(len(highs)), highs, 1)[0]
    low_slope = np.polyfit(range(len(lows)), lows, 1)[0]
    if high_slope < 0 and low_slope > 0:
        return True
    return False

# Check breakout
def check_breakout(df):
    last_close = df['close'].iloc[-1]
    recent_high = df['high'].iloc[-5:].max()
    recent_low = df['low'].iloc[-5:].min()
    if last_close > recent_high:
        return "BUY"
    elif last_close < recent_low:
        return "SELL"
    return None

# Main loop
while True:
    now = datetime.utcnow()
    if TRADING_START <= now.hour < TRADING_END:
        for asset in ASSETS:
            df = fetch_candles(asset, count=100)
            if df.empty or len(df) < MIN_CONSOLIDATION_CANDLES:
                continue

            # Indicators
            df['rsi'] = ta.RSI(df['close'], RSI_PERIOD)
            macd, macd_signal, _ = ta.MACD(df['close'], fastperiod=MACD_FAST, slowperiod=MACD_SLOW, signalperiod=MACD_SIGNAL)
            df['macd'] = macd
            df['macd_signal'] = macd_signal
            df['supertrend'] = supertrend(df)

            # Triangle detection
            if detect_triangle(df):
                signal = check_breakout(df)
                if signal:
                    # Confirm with indicators
                    last_rsi = df['rsi'].iloc[-1]
                    last_macd = df['macd'].iloc[-1]
                    last_macd_signal = df['macd_signal'].iloc[-1]
                    last_supertrend = df['supertrend'].iloc[-1]

                    confirm = False
                    if signal == "BUY" and last_rsi > 50 and last_macd > last_macd_signal and last_supertrend == 1:
                        confirm = True
                    elif signal == "SELL" and last_rsi < 50 and last_macd < last_macd_signal and last_supertrend == -1:
                        confirm = True

                    if confirm:
                        msg = f"{signal} signal for {asset} at {df['close'].iloc[-1]:.5f} (Time: {now.strftime('%H:%M:%S')} GMT)"
                        send_telegram_message(msg)
    
    # Wait for next candle
    time.sleep(TIMEFRAME)

