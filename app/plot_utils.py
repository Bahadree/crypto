import numpy as np
import pandas as pd

def create_trend_line(points, last_n_dates=None, extend=0, num_points=100):
    # Dash ve Flask uyumlu: Sadece son iki noktayı kullan, extend kadar ileri-geri uzat
    if points is None or len(points) < 2 or 'date' not in points:
        return None
    if isinstance(points, dict):
        points = pd.DataFrame(points)
    last_two = points.iloc[-2:]
    x = last_two['date'].map(pd.Timestamp.timestamp).values
    y = last_two.iloc[:, 1].values
    m = (y[1] - y[0]) / (x[1] - x[0])
    b = y[0] - m * x[0]
    # Periyot (frekans) belirle
    if last_n_dates is not None and len(last_n_dates) > 1:
        freq = (last_n_dates.iloc[-1] - last_n_dates.iloc[-2]).total_seconds()
    else:
        freq = 24*60*60
    # Geriye ve ileriye uzatma için x_start ve x_end'i ayarla
    x_start = x[0] + extend * freq
    x_end = x[1] - extend * freq
    # Eğer extend negatifse, x_start geriye, x_end ileriye uzar
    if x_start > x_end:
        x_start, x_end = x_end, x_start
    x_vals = np.linspace(x_start, x_end, num_points)
    y_vals = m * x_vals + b
    return [(t, y) for t, y in zip(x_vals, y_vals)]
