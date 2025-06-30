from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
import pandas as pd
import requests
import json
import os
from app.data_utils import fetch_binance_klines, add_indicators, find_support_resistance, fetch_chart_data
from app.plot_utils import create_trend_line

main = Blueprint('main', __name__)

SUPABASE_URL = "https://eeytaoodctkaekpdnkzb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVleXRhb29kY3RrYWVrcGRua3piIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTExMDM1MzYsImV4cCI6MjA2NjY3OTUzNn0.60MaYd-mnQa5Zu4BvhY9jky1AAQo58A-SCB7Y_Da56c"

def load_coins():
    with open(os.path.join(os.path.dirname(__file__), "coins.json"), encoding="utf-8") as f:
        return json.load(f)

def get_selected_symbol(request):
    symbol = (
        request.form.get('symbol')
        or request.form.get('hidden_symbol')
        or request.args.get('symbol')
        or session.get('last_symbol')
        or 'BTCUSDT'
    )
    if request.method == 'POST' and (request.form.get('symbol') or request.form.get('hidden_symbol')):
        session['last_symbol'] = symbol
    return symbol

@main.route('/', methods=['GET', 'POST'])
def index():
    # VIP bilgisini her sayfa yüklemesinde güncelle
    user_email = session.get('user_email')
    if user_email:
        session['is_vip'] = is_vip_from_supabase(user_email)
    return render_template('home.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    success = None
    # VIP bilgisini her sayfa yüklemesinde güncelle
    user_email = session.get('user_email')
    if user_email:
        session['is_vip'] = is_vip_from_supabase(user_email)
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        status_code, resp = supabase_signup(email, password)
        user_uuid = resp.get('user', {}).get('id') or resp.get('id')
        if 'user' in resp and resp['user'] and not resp.get('error'):
            if user_uuid:
                insert_user_to_custom_table(email, user_uuid)
            success = "Başarılı! Hesabınız oluşturuldu, onaylamak için e-posta adresinizi kontrol edin."
        else:
            msg = resp.get('msg') or resp.get('error_description') or resp.get('error')
            code = str(resp.get('code', '')).lower()
            if msg and ('already registered' in msg.lower() or code in ['user_already_registered', 'email_already_exists']):
                error = "Bu e-posta adresiyle zaten bir hesap var."
            elif not msg or msg == "{}":
                success = "Başarılı! Hesabınız oluşturuldu, onaylamak için e-posta adresinizi kontrol edin."
            else:
                error = msg
    return render_template('register.html', error=error, success=success)

@main.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        ok, resp = supabase_signin(email, password)
        if ok and 'access_token' in resp:
            session['user_email'] = email
            user_id = resp.get('user', {}).get('id') or resp.get('id')
            if user_id:
                session['user_id'] = user_id
                insert_user_to_custom_table(email, user_id)
            session['plan'] = get_user_plan(email)
            # VIP bilgisini girişte güncelle
            session['is_vip'] = is_vip_from_supabase(email)
            return redirect(url_for('main.index'))
        else:
            error = resp.get('msg') or resp.get('error_description') or "Kullanıcı adı veya şifre hatalı."
    # VIP bilgisini her sayfa yüklemesinde güncelle
    user_email = session.get('user_email')
    if user_email:
        session['is_vip'] = is_vip_from_supabase(user_email)
    return render_template('login.html', error=error)

@main.route('/logout')
def logout():
    session.pop('user_email', None)
    session.pop('is_vip', None)
    return redirect(url_for('main.index'))

@main.route('/buy', methods=['GET', 'POST'])
def buy():
    user_email = session.get('user_email')
    # VIP bilgisini her sayfa yüklemesinde güncelle
    if user_email:
        session['is_vip'] = is_vip_from_supabase(user_email)
    # Yönlendirme kaldırıldı, VIP kullanıcı da buy sayfasını görebilir
    # if user_email and session.get('is_vip'):
    #     return redirect(url_for('main.analysis'))
    if request.method == 'POST':
        user_uuid = session.get('user_id')
        plan = request.args.get('plan', 'basic')
        if user_email and user_uuid:
            if not user_exists_in_custom_table(user_email, user_uuid):
                insert_user_to_custom_table(user_email, user_uuid)
            # Plan güncelle
            plan_ok = set_user_plan(user_email, plan)
            vip_ok = set_vip_status(user_email, True)
            if plan_ok and vip_ok:
                session['is_vip'] = True
                session['plan'] = plan
                return jsonify({"success": True, "message": "Satın alma işlemi başarılı! VIP üyeliğiniz aktif edildi."})
            else:
                return jsonify({"success": False, "message": "VIP üyelik güncellenemedi. Lütfen tekrar deneyin."})
        else:
            return jsonify({"success": False, "message": "Oturum açmadan satın alma işlemi yapılamaz."})
    return render_template('buy.html')

@main.route('/favorite', methods=['POST'])
def favorite():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"success": False, "message": "Giriş yapmalısınız."})
    symbol = request.json.get('symbol')
    if not symbol:
        return jsonify({"success": False, "message": "Coin sembolü eksik."})
    from urllib.parse import quote
    email_quoted = quote(str(user_email).lower())
    url = f"{SUPABASE_URL}/rest/v1/users?email=eq.{email_quoted}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    resp = requests.get(url + "&select=favorites", headers=headers)
    favorites = []
    if resp.ok:
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            favorites = data[0].get("favorites") or []
    if symbol in favorites:
        favorites.remove(symbol)
    else:
        favorites.append(symbol)
    patch_data = {"favorites": favorites}
    patch_resp = requests.patch(url, headers=headers, json=patch_data)
    return jsonify({"success": patch_resp.ok})

@main.route('/analysis', methods=['GET', 'POST'])
def analysis():
    coins = load_coins()
    user_email = session.get('user_email')
    if user_email:
        session['is_vip'] = is_vip_from_supabase(user_email)
    favorite_symbols = []
    if user_email:
        from urllib.parse import quote
        email_quoted = quote(str(user_email).lower())
        url = f"{SUPABASE_URL}/rest/v1/users?email=eq.{email_quoted}&select=favorites"
        headers = {"apikey": SUPABASE_KEY}
        resp = requests.get(url, headers=headers)
        if resp.ok:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                favorite_symbols = data[0].get("favorites") or []
    symbol = get_selected_symbol(request)
    interval = request.form.get('interval', request.args.get('interval', '1d'))
    chart_type = request.form.get('chart_type', request.args.get('chart_type', 'candlestick'))
    df = fetch_binance_klines(symbol=symbol, interval=interval)
    df = add_indicators(df)
    support_points, resistance_points = find_support_resistance(df)
    chart_data = fetch_chart_data(df)
    last_n = 70
    last_n_dates = df['date'].iloc[-last_n:]
    support_df = pd.DataFrame(support_points)
    resistance_df = pd.DataFrame(resistance_points)
    support_trend = create_trend_line(support_df.iloc[-2:], last_n_dates, extend=40, num_points=100) if len(support_df) >= 2 else None
    resistance_trend = create_trend_line(resistance_df.iloc[-2:], last_n_dates, extend=40, num_points=100) if len(resistance_df) >= 2 else None
    chart_data['support_trend'] = support_trend if support_trend else []
    chart_data['resistance_trend'] = resistance_trend if resistance_trend else []
    market_comment = "Piyasa genel olarak yatay seyrediyor. Bitcoin ve Ethereum'da volatilite düşük. Yatırımcılar yeni bir trend için beklemede."
    news_list = [
        {"title": "Bitcoin 70.000$'ı Test Etti", "summary": "Bitcoin fiyatı kısa süreliğine 70.000$ seviyesini test etti. Analistler volatilitenin sürebileceğini belirtiyor.", "url": "https://www.coindesk.com/markets/2024/06/01/bitcoin-tests-70000/"},
        {"title": "Ethereum Güncellemesi Başarıyla Tamamlandı", "summary": "Ethereum ağında yapılan son güncelleme ile işlem ücretlerinde düşüş bekleniyor.", "url": "https://www.ethnews.com/ethereum-update-complete"},
        {"title": "SEC, Yeni Kripto ETF Başvurusunu İnceliyor", "summary": "ABD Menkul Kıymetler ve Borsa Komisyonu, yeni bir kripto ETF başvurusunu değerlendirmeye aldı.", "url": "https://www.bloomberg.com/news/crypto-etf-sec"}
    ]
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        import plotly
        traces = []
        chartType = chart_type
        chartData = chart_data
        if chartType == "candlestick":
            traces.append({
                "x": chartData["dates"],
                "open": chartData["open"],
                "high": chartData["high"],
                "low": chartData["low"],
                "close": chartData["close"],
                "type": "candlestick",
                "name": "Fiyat",
                "increasing": {"line": {"color": "green"}},
                "decreasing": {"line": {"color": "red"}}
            })
            if chartData.get("support_trend"):
                traces.append({
                    "x": [pt[0]*1000 for pt in chartData["support_trend"]],
                    "y": [pt[1] for pt in chartData["support_trend"]],
                    "type": "scatter",
                    "mode": "lines",
                    "name": "Destek Trend Çizgisi",
                    "line": {"color": "green", "dash": "dash"},
                    "legendgroup": "Destek Trend",
                    "showlegend": True,
                    "hovertemplate": "<b>Destek Trend Çizgisi</b><br>Tarih: %{x}<br>Fiyat: %{y:.2f}<extra></extra>"
                })
            if chartData.get("resistance_trend"):
                traces.append({
                    "x": [pt[0]*1000 for pt in chartData["resistance_trend"]],
                    "y": [pt[1] for pt in chartData["resistance_trend"]],
                    "type": "scatter",
                    "mode": "lines",
                    "name": "Direnç Trend Çizgisi",
                    "line": {"color": "red", "dash": "dash"},
                    "legendgroup": "Direnç Trend",
                    "showlegend": True,
                    "hovertemplate": "<b>Direnç Trend Çizgisi</b><br>Tarih: %{x}<br>Fiyat: %{y:.2f}<extra></extra>"
                })
        elif chartType == "rsi":
            traces.append({
                "x": chartData["dates"],
                "y": chartData["rsi"],
                "type": "scatter",
                "mode": "lines",
                "name": "RSI",
                "line": {"color": "orange"}
            })
        elif chartType == "macd":
            traces.append({
                "x": chartData["dates"],
                "y": chartData["macd"],
                "type": "scatter",
                "mode": "lines",
                "name": "MACD",
                "line": {"color": "cyan"}
            })
            traces.append({
                "x": chartData["dates"],
                "y": chartData["macd_signal"],
                "type": "scatter",
                "mode": "lines",
                "name": "MACD Signal",
                "line": {"color": "magenta"}
            })
        layout = {
            "title": "Mum Grafiği" if chartType == "candlestick" else ("RSI" if chartType == "rsi" else "MACD"),
            "xaxis": {"title": "Tarih", "rangeslider": {"visible": False}},
            "yaxis": {
                "title": "Fiyat" if chartType == "candlestick" else ("RSI" if chartType == "rsi" else "MACD"),
                "fixedrange": False
            },
            "dragmode": "pan",
            "template": "plotly_dark",
            "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
            "hovermode": "x unified" if chartType == "candlestick" else "closest",
            "height": 600,
            "paper_bgcolor": "#000",
            "plot_bgcolor": "#000"
        }
        config = {
            "scrollZoom": True,
            "displaylogo": False,
            "responsive": True,
            "modeBarButtonsToRemove": ["select2d", "lasso2d"],
            "doubleClick": "reset+autosize",
            "staticPlot": False
        }
        return jsonify({"traces": traces, "layout": layout, "config": config})

    # Sadece coingecko ile devam, diğer ikon url fonksiyonlarını ve parametrelerini kaldır
    return render_template(
        'analysis.html',
        chart_data=chart_data,
        support=support_points,
        resistance=resistance_points,
        symbol=symbol,
        interval=interval,
        chart_type=chart_type,
        coins=coins,
        favorite_symbols=favorite_symbols,
        market_comment=market_comment,
        news_list=news_list
    )

@main.route('/news', methods=['GET', 'POST'])
def news():
    coins = load_coins()
    user_email = session.get('user_email')
    if user_email:
        session['is_vip'] = is_vip_from_supabase(user_email)
    favorite_symbols = []
    if user_email:
        from urllib.parse import quote
        email_quoted = quote(str(user_email).lower())
        url = f"{SUPABASE_URL}/rest/v1/users?email=eq.{email_quoted}&select=favorites"
        headers = {"apikey": SUPABASE_KEY}
        resp = requests.get(url, headers=headers)
        if resp.ok:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                favorite_symbols = data[0].get("favorites") or []
    symbol = get_selected_symbol(request)
    CRYPTO_PANIC_API_KEY = "36a4023af447358b15943cec8ed5dab7aba09e4f"
    news_list = []
    try:
        url = (
            "https://cryptopanic.com/api/v1/posts/"
            f"?auth_token={CRYPTO_PANIC_API_KEY}"
            "&public=true"
            "&regions=tr"
            "&kind=news"
        )
        resp = requests.get(url)
        if resp.ok:
            data = resp.json()
            for item in data.get("results", []):
                title = item.get("title") or (item.get("source", {}) or {}).get("title") or ""
                summary = item.get("body") or item.get("description") or ""
                url_link = item.get("url", "#")
                if title or summary:
                    news_list.append({
                        "title": title if title else "(Başlık Yok)",
                        "summary": summary if summary else url_link,
                        "url": url_link
                    })
    except Exception as ex:
        # Hata ayıklama için log ekleyin
        print("Haber çekme hatası:", ex)
    return render_template(
        'news.html',
        news_list=news_list,
        coins=coins,
        favorite_symbols=favorite_symbols,
        symbol=symbol
    )

@main.route('/market_comment', methods=['GET', 'POST'])
def market_comment():
    coins = load_coins()
    user_email = session.get('user_email')
    if user_email:
        session['is_vip'] = is_vip_from_supabase(user_email)
    favorite_symbols = []
    if user_email:
        from urllib.parse import quote
        email_quoted = quote(str(user_email).lower())
        url = f"{SUPABASE_URL}/rest/v1/users?email=eq.{email_quoted}&select=favorites"
        headers = {"apikey": SUPABASE_KEY}
        resp = requests.get(url, headers=headers)
        if resp.ok:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                favorite_symbols = data[0].get("favorites") or []
    symbol = get_selected_symbol(request)
    market_comment = "Piyasa genel olarak yatay seyrediyor. Bitcoin ve Ethereum'da volatilite düşük. Yatırımcılar yeni bir trend için beklemede."

    sentiment_result = None
    if request.method == "POST" and (request.form.get("sentiment_text") or request.form.get("sentiment_text", "").strip()):
        text = request.form.get("sentiment_text", "").strip()
        try:
            import joblib
            import re, string, numpy as np
            from scipy.sparse import hstack
            model_path = os.path.join(os.path.dirname(__file__), "sentiment_model.joblib")
            vectorizer_path = os.path.join(os.path.dirname(__file__), "sentiment_vectorizer.joblib")
            scaler_path = os.path.join(os.path.dirname(__file__), "sentiment_scaler.joblib")
            if os.path.exists(model_path) and os.path.exists(vectorizer_path) and os.path.exists(scaler_path):
                model = joblib.load(model_path)
                vectorizer = joblib.load(vectorizer_path)
                scaler = joblib.load(scaler_path)
                def clean_text(text):
                    text = text.lower()
                    text = re.sub(rf"[{string.punctuation}]", "", text)
                    return text
                def extract_features(texts, prev_sentiments):
                    pos_words = ["yükseliş", "kazanc", "umut", "pozitif", "güçlü", "iyi", "güzel", "direnç"]
                    neg_words = ["düşüş", "panik", "kötü", "zarar", "kayıp", "endışe", "negatif", "destek"]
                    try:
                        import emoji
                    except ImportError:
                        emoji = None
                    pos_counts = [sum(word in t for word in pos_words) for t in texts]
                    neg_counts = [sum(word in t for word in neg_words) for t in texts]
                    emoji_scores = [sum(1 for char in t if emoji and char in getattr(emoji, "EMOJI_DATA", {})) for t in texts]
                    lengths = [len(t.split()) for t in texts]
                    uppercase_ratios = [sum(1 for c in t if c.isupper()) / max(len(t), 1) for t in texts]
                    exclamations = [t.count("!") for t in texts]
                    questions = [t.count("?") for t in texts]
                    prev_sents = prev_sentiments
                    features = np.array([pos_counts, neg_counts, emoji_scores, lengths,
                                         uppercase_ratios, exclamations, questions, prev_sents]).T
                    return features
                cleaned = clean_text(text)
                texts = [cleaned]
                prev_sentiments = [0]
                X_text = vectorizer.transform(texts)
                X_extra_raw = extract_features(texts, prev_sentiments)
                X_extra = scaler.transform(X_extra_raw)
                X = hstack([X_text, X_extra])
                pred = model.predict(X)[0]
                if pred == 1:
                    sentiment_result = "Olumlu"
                elif pred == -1:
                    sentiment_result = "Olumsuz"
                else:
                    sentiment_result = "Nötr"
            else:
                sentiment_result = "Model veya scaler bulunamadı"
        except Exception as e:
            sentiment_result = f"Hata: {e}"

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"result": sentiment_result})

    return render_template(
        'market_comment.html',
        market_comment=market_comment,
        coins=coins,
        favorite_symbols=favorite_symbols,
        symbol=symbol,
        sentiment_result=sentiment_result
    )

@main.route('/kvkk')
def kvkk():
    user_email = session.get('user_email')
    if user_email:
        session['is_vip'] = is_vip_from_supabase(user_email)
    return render_template('kvkk.html')

@main.route('/terms')
def terms():
    user_email = session.get('user_email')
    if user_email:
        session['is_vip'] = is_vip_from_supabase(user_email)
    return render_template('terms.html')

@main.route('/verify')
def verify():
    user_email = session.get('user_email')
    if user_email:
        session['is_vip'] = is_vip_from_supabase(user_email)
    return render_template('verify.html')

@main.route('/')
def root_render():
    return "Kriptoanaliz Web API çalışıyor."

# Eksik fonksiyon: is_vip_from_supabase
def is_vip_from_supabase(email):
    from urllib.parse import quote
    email_quoted = quote(str(email).lower())
    url = f"{SUPABASE_URL}/rest/v1/users?email=eq.{email_quoted}&select=vip"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    }
    resp = requests.get(url, headers=headers)
    try:
        if resp.ok:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return bool(data[0].get("vip", False))
    except Exception:
        pass
    return False

# Supabase login fonksiyonu eksikti, ekleniyor:
def supabase_signin(email, password):
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "email": email,
        "password": password
    }
    resp = requests.post(url, headers=headers, json=data)
    try:
        if resp.ok:
            return True, resp.json()
        else:
            return False, resp.json()
    except Exception:
        return False, {"error": "Sunucu hatası"}

# Supabase signup fonksiyonu eksikti, ekleniyor:
def supabase_signup(email, password):
    url = f"{SUPABASE_URL}/auth/v1/signup"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "email": email,
        "password": password
    }
    resp = requests.post(url, headers=headers, json=data)
    try:
        if resp.ok:
            return resp.status_code, resp.json()
        else:
            return resp.status_code, resp.json()
    except Exception:
        return 500, {"error": "Sunucu hatası"}

# Eksik fonksiyon: insert_user_to_custom_table
def insert_user_to_custom_table(email, user_uuid):
    from urllib.parse import quote
    email_quoted = quote(str(email).lower())
    url = f"{SUPABASE_URL}/rest/v1/users"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    data = {
        "email": email,
        "uuid": user_uuid
    }
    # Upsert (varsa güncelle, yoksa ekle)
    resp = requests.post(url, headers=headers, json=data)
    return resp.ok

def set_user_plan(email, plan_name):
    from urllib.parse import quote
    email_quoted = quote(str(email).lower())
    url = f"{SUPABASE_URL}/rest/v1/users?email=eq.{email_quoted}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    patch_data = {"plan": plan_name}
    resp = requests.patch(url, headers=headers, json=patch_data)
    return resp.ok

def get_user_plan(email):
    from urllib.parse import quote
    email_quoted = quote(str(email).lower())
    url = f"{SUPABASE_URL}/rest/v1/users?email=eq.{email_quoted}&select=plan"
    headers = {"apikey": SUPABASE_KEY}
    resp = requests.get(url, headers=headers)
    if resp.ok:
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0].get("plan", "free")
    return "free"

def user_exists_in_custom_table(email, user_uuid):
    from urllib.parse import quote
    email_quoted = quote(str(email).lower())
    url = f"{SUPABASE_URL}/rest/v1/users?email=eq.{email_quoted}&uuid=eq.{user_uuid}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    }
    resp = requests.get(url, headers=headers)
    if resp.ok:
        data = resp.json()
        return isinstance(data, list) and len(data) > 0
    return False

def set_vip_status(email, is_vip=True):
    from urllib.parse import quote
    email_quoted = quote(str(email).lower())
    url = f"{SUPABASE_URL}/rest/v1/users?email=eq.{email_quoted}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    patch_data = {"vip": is_vip}
    resp = requests.patch(url, headers=headers, json=patch_data)
    return resp.ok
