from functools import wraps
from flask import g, request, redirect, url_for, jsonify

def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.get("current_user"):
            next_url = request.path
            return redirect(url_for("auth.login_page", next=next_url))
        return view(*args, **kwargs)
    return wrapper

def role_required_page(roles: list[str]):
    def deco(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            cu = g.get("current_user")
            if not cu:
                next_url = request.path
                return redirect(url_for("auth.login_page", next=next_url))
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
