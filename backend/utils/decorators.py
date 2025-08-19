from functools import wraps
from flask import g, request, redirect, url_for, jsonify, current_app
import logging

def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.get("current_user"):
            next_url = request.path
            return redirect(url_for("pages_auth.login_page", next=next_url))
        return view(*args, **kwargs)
    return wrapper

def role_required_page(roles: list[str]):
    def deco(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            cu = g.get("current_user")
            if not cu:
                next_url = request.path
                return redirect(url_for("pages_auth.login_page", next=next_url))
            if cu.get("role") not in roles:
                # 403 o redirigir a su home
                return redirect("/")
            return view(*args, **kwargs)
        return wrapper
    return deco

# Para endpoints JSON / APIs
def api_auth_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.get("current_user"):
            return jsonify({"error": "unauthorized"}), 401
        return view(*args, **kwargs)
    return wrapper

def api_role_required(roles: list[str]):
    def deco(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            cu = g.get("current_user")
            if not cu:
                return jsonify({"error": "unauthorized"}), 401
            if cu.get("role") not in roles:
                return jsonify({"error": "forbidden"}), 403
            return view(*args, **kwargs)
        return wrapper
    return deco

# Decorador para verificar si el coordinador debe cambiar su contraseña
def coord_pw_changed_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        cu = g.get("current_user")
        # Solo aplica para coordinadores
        if cu and cu.get("role") == "coordinator":
            # Debes tener una función que verifique el estado, por ejemplo:
            from models import Coordinator
            coord = Coordinator.query.filter_by(user_id=cu["sub"]).first()
            current_app.logger.warning("Verificando si el coordinador debe cambiar su contraseña" + str(getattr(coord, "must_change_pw", False)) )
            if coord and getattr(coord, "must_change_pw", False):
                # Redirige a home del coordinador (donde está el modal)
                return redirect(url_for("coord_pages.coord_home_page"))
        return view(*args, **kwargs)
    return wrapper