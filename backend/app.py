import os
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, login_required
from datetime import timedelta
from models import User
from models import db
from routes.auth import auth_bp

login_manager = LoginManager()

def create_app():
    app = Flask(__name__, static_url_path="/static", static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
    app.config["JWT_EXPIRES_HOURS"] = int(os.getenv("JWT_EXPIRES_HOURS", "12"))
    app.config["COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    app.config["COOKIE_SAMESITE"] = os.getenv("COOKIE_SAMESITE", "Lax")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///dev.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Por favor, inicia sesión para continuar."
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    register_blueprints(app)

    app.permanent_session_lifetime = timedelta(minutes=20)

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/")
    def home():
        return redirect(url_for("auth.login_page"))

    # Demos de dashboard por rol (placeholders)
    @app.get("/student/home")
    @login_required
    def student_home():
        return "Student dashboard (placeholder)"

    @app.get("/coord/home")
    @login_required
    def coord_home():
        return "Coordinator dashboard (placeholder)"

    @app.get("/social/home")
    @login_required
    def social_home():
        return "Social service dashboard (placeholder)"

    return app

def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix="/auth")
