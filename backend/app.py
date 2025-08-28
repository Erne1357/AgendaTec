import os, time 
from flask import Flask, render_template, redirect, url_for, request,current_app,g,jsonify
from models import db
from utils.jwt_tools import encode_jwt, decode_jwt
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from utils.admit_window import is_student_window_open, get_student_window


import logging


def create_app():
    app = Flask(__name__, static_url_path="/static", static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
    app.config["JWT_EXPIRES_HOURS"] = int(os.getenv("JWT_EXPIRES_HOURS", "12"))
    app.config["COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    app.config["COOKIE_SAMESITE"] = os.getenv("COOKIE_SAMESITE", "Lax")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///dev.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JWT_REFRESH_THRESHOLD_SECONDS"] = 2 * 3600 
    app.config["STATIC_VERSION"] = "1.0.22233479"  


    db.init_app(app)
    register_blueprints(app)
    register_error_handlers(app)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


    from sockets import init_socketio
    init_socketio(app)

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

    @app.teardown_request
    def cleanup_db(exc=None):
        # Si hubo excepción durante el request, revierte cualquier transacción pendiente
        if exc is not None:
            try:
                db.session.rollback()
            except Exception:
                pass
        # En todos los casos, limpia la sesión para evitar fugas/conexiones colgadas
        try:
            db.session.remove()
        except Exception:
            pass

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/")
    def home():
        if g.current_user:
            return redirect(role_home(g.current_user.get("role")))
        return redirect(url_for("pages_auth.login_page"))
    
    @app.context_processor
    def inject_globals():
        _student_open = is_student_window_open()
        _win = get_student_window()

        def _icon_for(label: str) -> str:
            lbl = (label or "").lower()
            if "dashboard" in lbl: return "bi-grid"
            if "coordinador" in lbl: return "bi-person-gear"
            if "cita" in lbl: return "bi-calendar2-check"
            if "horario" in lbl: return "bi-clock"
            if "bajas" in lbl: return "bi-arrow-down-circle"
            if "servicio social" in lbl: return "bi-people"
            if "inicio" in lbl: return "bi-house"
            if "mis solicitudes" in lbl: return "bi-file-earmark-text"
            if "usuarios" in lbl: return "bi-people"
            if "solicitudes" in lbl: return "bi-journal-text"
            if "reportes" in lbl: return "bi-bar-chart"
            if "encuestas" in lbl: return "bi-clipboard2-check"
            return "bi-grid"

        def is_active(url: str) -> bool:
            # activo si coincide exactamente o si la ruta actual cuelga de ese url
            p = request.path
            return p == url or p.startswith(url + "/")

        def nav_for(role: str | None):
            # ----- Definición del árbol de navegación -----
            social = [
                {"label": "Citas", "endpoint": "social_pages.social_home",
                "roles": ["social_service"]}
            ]
            student = [
                {"label": "Inicio", "endpoint": "student_pages.student_home", "roles": ["student"]},
                {"label": "Mis solicitudes", "endpoint": "student_pages.student_requests", "roles": ["student"]},
            ]
            coord = [
                {"label": "Dashboard", "endpoint": "coord_pages.coord_home_page", "roles": ["coordinator"]},
                {"label": "Horario ", "endpoint": "coord_pages.coord_slots_page", "roles": ["coordinator"]},
                {"label": "Citas del día", "endpoint": "coord_pages.coord_appointments_page", "roles": ["coordinator"]},
                {"label": "Bajas", "endpoint": "coord_pages.coord_drops_page", "roles": ["coordinator"]},
            ]
            admin_items = [
                {"label":"Dashboard","endpoint":"admin_pages.admin_home","roles":["admin"]},
                {"label":"Usuarios","endpoint":"admin_pages.admin_users","roles":["admin"]},
                {"label":"Solicitudes","endpoint":"admin_pages.admin_requests","roles":["admin"]},
                {"label":"Reportes","endpoint":"admin_pages.admin_reports","roles":["admin"]},
                {"label":"Encuestas","endpoint":"admin_surveys_pages.admin_surveys","roles":["admin"]},
            ]
            all_items = student + coord + social + admin_items
            if not role:
                return []
            
            if role == "student" and not _student_open:
                return []

            # ----- Filtrar por rol -----
            filtered = [it for it in all_items if role in it["roles"]]

            # ----- Quitar duplicados y enriquecer con url + icon -----
            seen: set[tuple[str, str]] = set()
            dedup_enriched: list[dict] = []
            for it in filtered:
                key = (it["label"], it["endpoint"])
                if key in seen:
                    continue
                seen.add(key)
                dedup_enriched.append({
                    "label": it["label"],
                    "endpoint": it["endpoint"],
                    "url": url_for(it["endpoint"]),
                    "icon": _icon_for(it["label"]),
                })
            return dedup_enriched

        return {
            "current_user": g.current_user,
            "static_version": current_app.config.get("STATIC_VERSION", "1.0.0"),
            "nav_for": nav_for,
            "is_active": is_active,
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
    from routes.api.social import api_social_bp
    from routes.api.admin import api_admin_bp
    from routes.api.notifications import api_notifications_bp
    app.register_blueprint(api_auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(api_programs_bp, url_prefix="/api/v1")
    app.register_blueprint(api_avail_bp, url_prefix="/api/v1")
    app.register_blueprint(api_req_bp, url_prefix="/api/v1")
    app.register_blueprint(api_slots_bp, url_prefix="/api/v1")
    app.register_blueprint(api_coord_bp, url_prefix="/api/v1")
    app.register_blueprint(api_social_bp,url_prefix="/api/v1")
    app.register_blueprint(api_admin_bp, url_prefix="/api/v1/admin")
    app.register_blueprint(api_notifications_bp,url_prefix="/api/v1")

    #Register blueprints for pages
    from routes.pages.auth import pages_auth_bp
    from routes.pages.student import student_pages_bp
    from routes.pages.coord import coord_pages_bp
    from routes.pages.social import social_pages_bp
    from routes.pages.admin import admin_pages_bp
    from routes.pages.admin_surveys import admin_surveys_pages
    app.register_blueprint(social_pages_bp, url_prefix="/social")
    app.register_blueprint(pages_auth_bp, url_prefix="/auth")
    app.register_blueprint(student_pages_bp, url_prefix="/student")
    app.register_blueprint(coord_pages_bp, url_prefix="/coord")
    app.register_blueprint(admin_pages_bp, url_prefix="/admin")
    app.register_blueprint(admin_surveys_pages)

def role_home(role: str) -> str:
        return { "student": "/student/home",
                 "coordinator": "/coord/home",
                 "social_service": "/social/home",
                  "admin":"/admin/home" }.get(role, "/")

def register_error_handlers(app):
    MESSAGES = {
        400: "Solicitud inválida",
        401: "No autenticado",
        403: "Acceso prohibido",
        404: "Recurso no encontrado",
        405: "Método no permitido",
        409: "Conflicto de recurso",
        413: "Carga demasiado grande",
        415: "Tipo de contenido no soportado",
        429: "Demasiadas solicitudes",
        500: "Error interno del servidor",
        502: "Puerta de enlace inválida",
        503: "Servicio no disponible",
        504: "Tiempo de espera agotado",
    }

    BIG_PAGE_CODES = {404, 405, 500, 502, 503, 504}

    def wants_json():
        return request.path.startswith("/api/")

    def render_error_page(status_code, message):
        # Usa una plantilla única con tu animación; recibe code & message
        return render_template("errors/error_page.html",
                               code=status_code,
                               message=message), status_code

    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException):
        code = e.code or 500
        msg = MESSAGES.get(code, e.name or "Error")
        # JSON para API
        if wants_json():
            payload = {"error": getattr(e, "name", "error"), "status": code}
            # Si hay descripción útil, inclúyela
            if getattr(e, "description", None):
                payload["detail"] = e.description
            return jsonify(payload), code

        # Páginas: 401 → login; grandes → plantilla; resto → plantilla genérica también
        if code == 401:
            # puedes agregar ?next=<ruta_actual>
            return redirect(url_for("pages_auth.login_page"))
        page_code = code if code in MESSAGES else 500
        return render_error_page(page_code, msg)

    @app.errorhandler(Exception)
    def handle_unexpected(e: Exception):
        app.logger.exception("Unhandled exception")
        if wants_json():
            return jsonify({"error": "internal_error", "status": 500}), 500
        return render_error_page(500, MESSAGES[500])

    # Opcional: handlers explícitos (si quieres sobreescribir mensajes)
    for code in [400,401,403,404,405,409,413,415,429,500,502,503,504]:
        def _factory(c):
            def _h(_e):
                if wants_json():
                    return jsonify({"error": _e.name if isinstance(_e, HTTPException) else "error", "status": c}), c
                if c == 401:
                    return redirect(url_for("pages_auth.login_page"))
                return render_error_page(c, MESSAGES.get(c, "Error"))
            return _h
        app.register_error_handler(code, _factory(code))