from flask import Blueprint, request, jsonify, make_response, current_app,render_template
from utils.jwt_tools import encode_jwt, decode_jwt
from services.auth_service import authenticate

auth_bp = Blueprint("auth", __name__)

@auth_bp.get("/login")
def login_page():
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
        {"sub": user["id"], "role": user["role"], "cn": user["control_number"], "name": user["full_name"]},
        hours=current_app.config["JWT_EXPIRES_HOURS"]
    )
    resp = make_response({"user":{"id":user["id"],"role":user["role"],"full_name":user["full_name"]}})
    resp.set_cookie(
        "agendatec_token",
        token,
        httponly=True,
        samesite=current_app.config.get("COOKIE_SAMESITE","Lax"),
        secure=current_app.config.get("COOKIE_SECURE", False),
        max_age=current_app.config["JWT_EXPIRES_HOURS"]*3600,
        path="/"
    )
    return resp

@auth_bp.get("/me")
def me():
    token = request.cookies.get("agendatec_token")
    data = decode_jwt(token) if token else None
    if not data:
        return jsonify({"error":"unauthorized"}), 401
    return jsonify({"user":{"id":data["sub"],"role":data["role"],"control_number":data["cn"],"full_name":data.get("name","")}})

@auth_bp.post("/logout")
def logout():
    resp = make_response({}, 204)
    resp.set_cookie("agendatec_token", "", expires=0, httponly=True, samesite=current_app.config.get("COOKIE_SAMESITE","Lax"),
                    secure=current_app.config.get("COOKIE_SECURE", False), path="/")
    return resp
