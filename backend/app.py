import os, time 
from flask import Flask, render_template, redirect, url_for, request,current_app,g
from models import db
from utils.jwt_tools import encode_jwt, decode_jwt
from utils.decorators import login_required, role_required_page, api_auth_required, api_role_required   

def create_app():
    app = Flask(__name__, static_url_path="/static", static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
    app.config["JWT_EXPIRES_HOURS"] = int(os.getenv("JWT_EXPIRES_HOURS", "12"))
    app.config["COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    app.config["COOKIE_SAMESITE"] = os.getenv("COOKIE_SAMESITE", "Lax")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///dev.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JWT_REFRESH_THRESHOLD_SECONDS"] = 2 * 3600 
    app.config["STATIC_VERSION"] = "1.0.2"  

    db.init_app(app)

    register_blueprints(app)

    @app.before_request
    def load_current_user():
        g.current_user = None
        token = request.cookies.get("agendatec_token")
        data = decode_jwt(token) if token else None
        if data:
            g.current_user = data  # dict con sub, role, cn, name, iat, exp
            # bandera para refrescar si expira pronto
            now = int(time.time())
            if data.get("exp", 0) - now < app.config["JWT_REFRESH_THRESHOLD_SECONDS"]:
                g._refresh_token = True
        else:
            g._refresh_token = False

    @app.after_request
    def maybe_refresh_cookie(resp):
        if getattr(g, "_refresh_token", False) and g.current_user:
            new_token = encode_jwt(
                {"sub": g.current_user["sub"], "role": g.current_user["role"],
                 "cn": g.current_user.get("cn"), "name": g.current_user.get("name")},
                hours=current_app.config["JWT_EXPIRES_HOURS"]
            )
            resp.set_cookie(
                "agendatec_token", new_token, httponly=True,
                samesite=current_app.config["COOKIE_SAMESITE"],
                secure=current_app.config["COOKIE_SECURE"],
                max_age=current_app.config["JWT_EXPIRES_HOURS"] * 3600,
                path="/"
            )
        return resp

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/")
    def home():
        if g.current_user:
            return redirect(role_home(g.current_user.get("role")))
        return redirect(url_for("pages_auth.login_page"))



    @app.get("/coord/home")
    @login_required
    @role_required_page(["coordinator"])
    def coord_home():
        return "Coordinator dashboard (placeholder)"

    @app.get("/social/home")
    @login_required
    @role_required_page(["social_service"])
    def social_home():
        return "Social service dashboard (placeholder)"
    
    @app.context_processor
    def inject_globals():
        def nav_for(role: str | None):
            # Estructura de menú basada en páginas. Puedes ajustar labels/orden.
            base = [
                # Entradas compartidas por múltiples roles
                {"label": "Citas (Servicio Social)", "endpoint": "social_pages.social_home",
                 "roles": ["social_service","coordinator","admin"]},
                {"label": "Panel coordinador", "endpoint": "coord_pages.coord_home_page",
                 "roles": ["coordinator","admin"]},
            ]
            # Estudiante
            student = [
                {"label": "Inicio", "endpoint": "student_pages.student_home", "roles": ["student"]},
                {"label": "Mis solicitudes", "endpoint": "student_pages.student_requests", "roles": ["student"]},
            ]
            # Coordinador
            coord = [
                {"label": "Mi horario / slots", "endpoint": "coord_pages.coord_home_page", "roles": ["coordinator","admin"]},
                {"label": "Citas del día", "endpoint": "coord_pages.coord_appointments_page", "roles": ["coordinator","admin"]},
                {"label": "Drops", "endpoint": "coord_pages.coord_drops_page", "roles": ["coordinator","admin"]},
            ]
            # Social
            social = [
                {"label": "Citas (día)", "endpoint": "social_pages.social_home", "roles": ["social_service","coordinator","admin"]},
            ]

            all_items = base + student + coord + social
            if not role:  # no logueado
                return []
            return [it for it in all_items if role in it["roles"]]

        return {
            "current_user": g.current_user,
            "static_version": current_app.config.get("STATIC_VERSION", "1.0.0"),
            "nav_for": nav_for
        }
    return app

def register_blueprints(app):
    # Register blueprints for apis
    from routes.api.auth import api_auth_bp
    from routes.api.programs_academic import api_programs_bp
    from routes.api.availability import api_avail_bp
    from routes.api.requests import api_req_bp
    from routes.api.slots import api_slots_bp
    from routes.api.coord import api_coord_bp
    app.register_blueprint(api_auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(api_programs_bp, url_prefix="/api/v1")
    app.register_blueprint(api_avail_bp, url_prefix="/api/v1")
    app.register_blueprint(api_req_bp, url_prefix="/api/v1")
    app.register_blueprint(api_slots_bp, url_prefix="/api/v1")
    app.register_blueprint(api_coord_bp, url_prefix="/api/v1")

    #Register blueprints for pages
    from routes.pages.auth import pages_auth_bp
    from routes.pages.student import student_pages_bp
    from routes.pages.coord import coord_pages_bp
    from routes.pages.social import social_pages_bp
    app.register_blueprint(social_pages_bp, url_prefix="/social")
    app.register_blueprint(pages_auth_bp, url_prefix="/auth")
    app.register_blueprint(student_pages_bp, url_prefix="/student")
    app.register_blueprint(coord_pages_bp, url_prefix="/coord")

def role_home(role: str) -> str:
        return { "student": "/student/home",
                 "coordinator": "/coord/home",
                 "social_service": "/social/home" }.get(role, "/")
