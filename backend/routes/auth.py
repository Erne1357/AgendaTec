from flask import Blueprint, request, jsonify, make_response,render_template,redirect, current_app,render_template, g
from utils.jwt_tools import encode_jwt, decode_jwt
from services.auth_service import authenticate
from app import role_home

auth_bp = Blueprint("auth", __name__)

@auth_bp.get("/login")
def login_page():
    if g.current_user:
        return redirect(role_home(g.current_user.get("role")))
    return render_template("auth/login.html")

@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    cn, nip = (data.get("control_number","") or "").strip(), (data.get("nip","") or "").strip()
    if not (cn.isdigit() and len(cn)==8 and nip.isdigit() and len(nip)==4):
        return jsonify({"error":"invalid_format"}), 400

    user = authenticate(cn, nip)
    if not user:
        return jsonify({"error":"invalid_credentials"}), 401

    token = encode_jwt(
        {"sub": str(user["id"]), "role": user["role"], "cn": user["control_number"], "name": user["full_name"]},
        hours=current_app.config["JWT_EXPIRES_HOURS"]
    )
    resp = make_response({"user":{"id":user["id"],"role":user["role"],"full_name":user["full_name"]}})
    resp.set_cookie(
        "agendatec_token", token, httponly=True,
        samesite=current_app.config["COOKIE_SAMESITE"],
        secure=current_app.config["COOKIE_SECURE"],
        max_age=current_app.config["JWT_EXPIRES_HOURS"]*3600,
        path="/"
    )
    return resp

@auth_bp.get("/me")
def me():
    token = request.cookies.get("agendatec_token")
    current_app.logger.info("ME: cookie len=%s head=%s",
                            len(token) if token else 0,
                            token[:16] + "..." if token else None)
    data = decode_jwt(token) if token else None
    if not data:
        return jsonify({"error":"unauthorized "}),401
    return jsonify({"user":{"id":data["sub"],"role":data["role"],"control_number":data["cn"],"full_name":data.get("name","")}})

@auth_bp.post("/logout")
def logout():
    resp = make_response({}, 204)
    resp.set_cookie("agendatec_token", "", expires=0, httponly=True,
                    samesite=current_app.config["COOKIE_SAMESITE"],
                    secure=current_app.config["COOKIE_SECURE"],
                    path="/")
    return resp
