import pandas as pd
import numpy as np
import requests
import streamlit as st

# Fetch data from Binance API
def fetch_data(symbol='XRPUSDT', interval='1m'):
    url = 'https://api.binance.com/api/v3/klines'
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': 100  # Get 100 data points for better analysis
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list) or len(data) == 0 or not isinstance(data[0], list):
            st.warning("Unexpected data format received.")
            return pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
        
        # Extract relevant fields
        o, h, l, c, v = zip(*[(float(d[1]), float(d[2]), float(d[3]), float(d[4]), float(d[5])) for d in data])
        datetime = pd.to_datetime([d[0] for d in data], unit='ms')
        
        return pd.DataFrame({
            'datetime': datetime,
            'open': o,
            'high': h,
            'low': l,
            'close': c,
            'volume': v
        })
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])

# Update signals based on new data
def update_signals():
    global df
    new_data = fetch_data()
    
    if new_data.empty:
        st.warning("No new data fetched.")
        return None, None, None
    
    # Append new data to the existing DataFrame
    df = pd.concat([df, new_data], ignore_index=True)
    
    # Ensure DataFrame is not too large
    if len(df) > 100:
        df = df.iloc[-100:]
    
    # Calculate ATR and EMA
    df['high-low'] = df['high'] - df['low']
    df['high-close_prev'] = np.abs(df['high'] - df['close'].shift(1))
    df['low-close_prev'] = np.abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['high-low', 'high-close_prev', 'low-close_prev']].max(axis=1)
    df['atr'] = df['tr'].rolling(window=c, min_periods=1).mean()
    
    df['nLoss'] = a * df['atr']
    df['xATRTrailingStop'] = np.nan
    
    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['xATRTrailingStop'].iloc[i-1] and df['close'].iloc[i-1] > df['xATRTrailingStop'].iloc[i-1]:
            df['xATRTrailingStop'].iloc[i] = max(df['xATRTrailingStop'].iloc[i-1], df['close'].iloc[i] - df['nLoss'].iloc[i])
        elif df['close'].iloc[i] < df['xATRTrailingStop'].iloc[i-1] and df['close'].iloc[i-1] < df['xATRTrailingStop'].iloc[i-1]:
            df['xATRTrailingStop'].iloc[i] = min(df['xATRTrailingStop'].iloc[i-1], df['close'].iloc[i] + df['nLoss'].iloc[i])
        elif df['close'].iloc[i] > df['xATRTrailingStop'].iloc[i-1]:
            df['xATRTrailingStop'].iloc[i] = df['close'].iloc[i] - df['nLoss'].iloc[i]
        else:
            df['xATRTrailingStop'].iloc[i] = df['close'].iloc[i] + df['nLoss'].iloc[i]
    
    df['ema'] = df['close'].ewm(span=1, adjust=False).mean()
    
    df['above'] = df['ema'] > df['xATRTrailingStop']
    df['below'] = df['ema'] < df['xATRTrailingStop']
    
    df['buy'] = (df['close'] > df['xATRTrailingStop']) & df['above']
    df['sell'] = (df['close'] < df['xATRTrailingStop']) & df['below']
    
    df['signal'] = np.nan
    df.loc[df['buy'], 'signal'] = 'Buy'
    df.loc[df['sell'], 'signal'] = 'Sell'
    
    if len(df) > 0:
        latest_signal = df.iloc[-1]
        if latest_signal['buy']:
            return 'Buy', latest_signal['close'], latest_signal['datetime']
        elif latest_signal['sell']:
            return 'Sell', latest_signal['close'], latest_signal['datetime']
        else:
            return 'Hold', None, latest_signal['datetime']
    else:
        return None, None, None

# Parameters for ATR calculation and window size
a = 1
c = 10

# Initialize DataFrame with historical data
df = pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])

# Streamlit UI setup
st.title("XRP/USDT Trading Signal with Dynamic Updates")
st.write("This app fetches data from Binance and generates trading signals.")

if st.button("Fetch Signal"):
    signal, price, timestamp = update_signals()
    if signal and price:
        st.write(f"Signal: {signal} at {timestamp}, Price: {price}")
    else:
        st.write("No new signal available.")
