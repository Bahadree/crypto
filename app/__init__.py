from flask import Flask

def create_app():
    app = Flask(__name__)
    # Buraya kendi güçlü ve rastgele secret key'inizi kendiniz girmelisiniz!
    app.secret_key = "8f3b1c2d4e5f6a7b8c9d0e1f2a3b4c5d"
    from .routes import main
    if 'main' not in app.blueprints:
        app.register_blueprint(main)
    
    return app