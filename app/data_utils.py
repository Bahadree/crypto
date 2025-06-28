import requests
import pandas as pd
import ta
from scipy.signal import argrelextrema

MAX_CANDLES = 500

def fetch_binance_klines(symbol='BTCUSDT', interval='1d', limit=MAX_CANDLES):
    url = 'https://api.binance.com/api/v3/klines'
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    r = requests.get(url, params=params)
    data = r.json()
    df = pd.DataFrame(data, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    df['date'] = pd.to_datetime(df['open_time'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    return df[['date', 'open', 'high', 'low', 'close', 'volume']]

def add_indicators(df):
    df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
    macd = ta.trend.MACD(close=df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    return df

def find_support_resistance(df, order=5):
    import numpy as np
    local_min_idx = argrelextrema(df['low'].values, np.less_equal, order=order)[0]
    support_points = df.iloc[local_min_idx][['date', 'low']].to_dict(orient='records')
    local_max_idx = argrelextrema(df['high'].values, np.greater_equal, order=order)[0]
    resistance_points = df.iloc[local_max_idx][['date', 'high']].to_dict(orient='records')
    return support_points, resistance_points

def fetch_chart_data(df):
    # Grafik için gerekli verileri hazırla
    return {
        'dates': df['date'].dt.strftime('%Y-%m-%d %H:%M').tolist(),
        'open': df['open'].tolist(),
        'high': df['high'].tolist(),
        'low': df['low'].tolist(),
        'close': df['close'].tolist(),
        'volume': df['volume'].tolist(),
        'rsi': df['rsi'].fillna('').tolist() if 'rsi' in df else [],
        'macd': df['macd'].fillna('').tolist() if 'macd' in df else [],
        'macd_signal': df['macd_signal'].fillna('').tolist() if 'macd_signal' in df else [],
    }