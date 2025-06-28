from flask import Blueprint, render_template, request
import pandas as pd
from app.data_utils import fetch_binance_klines, add_indicators, find_support_resistance, fetch_chart_data
from app.plot_utils import create_trend_line

main = Blueprint('main', __name__)

@main.route('/', methods=['GET', 'POST'])
def index():
    symbol = request.form.get('symbol', 'BTCUSDT')
    interval = request.form.get('interval', '1d')
    chart_type = request.form.get('chart_type', 'candlestick')
    df = fetch_binance_klines(symbol=symbol, interval=interval)
    df = add_indicators(df)
    support_points, resistance_points = find_support_resistance(df)
    chart_data = fetch_chart_data(df)
    # --- Trend çizgileri için: son iki noktayı kullan, extend'i pozitif yaparak ileriye uzat ---
    last_n = 70
    last_n_dates = df['date'].iloc[-last_n:]
    support_df = pd.DataFrame(support_points)
    resistance_df = pd.DataFrame(resistance_points)
    support_trend = None
    resistance_trend = None
    if len(support_df) >= 2:
        # Buradaki extend parametresi çizginin uzunluğunu belirler (ör: extend=10)
        support_trend = create_trend_line(support_df.iloc[-2:], last_n_dates, extend=40, num_points=100)
    if len(resistance_df) >= 2:
        resistance_trend = create_trend_line(resistance_df.iloc[-2:], last_n_dates, extend=40, num_points=100)
    chart_data['support_trend'] = support_trend if support_trend else []
    chart_data['resistance_trend'] = resistance_trend if resistance_trend else []
    return render_template(
        'index.html',
        chart_data=chart_data,
        support=support_points,
        resistance=resistance_points,
        symbol=symbol,
        interval=interval,
        chart_type=chart_type
    )