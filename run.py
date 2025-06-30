import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    # Render.com için debug kapalı olmalı
    app.run(host='0.0.0.0', port=port, debug=False)