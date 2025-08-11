from flask import Flask, render_template

def create_app():
    app = Flask(__name__, static_url_path="/static", static_folder="static", template_folder="templates")

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/")
    def index():
        return render_template("index.html")

    return app
