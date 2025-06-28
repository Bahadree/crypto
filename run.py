from app import create_app

app = create_app()

if __name__ == '__main__':
    # Render.com için host ve port ayarları
    import os
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)