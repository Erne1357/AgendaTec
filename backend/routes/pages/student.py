# routes/pages/student.py
from flask import Blueprint, render_template
from utils.decorators import login_required, role_required_page

pages_student_bp = Blueprint("pages_student", __name__)

@pages_student_bp.get("/home")
@login_required
@role_required_page(["student"])
def student_home():
<<<<<<< Updated upstream
    return render_template("student/home.html")
=======
    return render_template("student/home.html", title="Alumno - Inicio")

@student_pages_bp.get("/requests")
@login_required
@role_required_page(["student"])
def student_requests():
    return render_template("student/requests.html", title="Alumno - Mis solicitudes")

@student_pages_bp.get("/student/request")
@login_required
@role_required_page(["student"])
def student_new_request():
    return render_template("student/new_request.html", title="Alumno - Nueva solicitud")
>>>>>>> Stashed changes
