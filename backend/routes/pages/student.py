# routes/pages/student.py
from flask import Blueprint, render_template
from utils.decorators import login_required, role_required_page

pages_student_bp = Blueprint("pages_student", __name__)

@pages_student_bp.get("/home")
@login_required
@role_required_page(["student"])
def student_home():
    return render_template("student/home.html", title="Alumno - Inicio")

@pages_student_bp.get("/requests")
@login_required
@role_required_page(["student"])
def student_requests():
    return render_template("student/requests.html", title="Alumno - Mis solicitudes")

@pages_student_bp.get("/request")
@login_required
@role_required_page(["student"])
def student_new_request():
    return render_template("student/new_request.html", title="Alumno - Nueva solicitud")
