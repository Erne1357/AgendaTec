# routes/templates/coord.py
from flask import Blueprint, render_template
from utils.decorators import login_required, role_required_page

coord_pages_bp = Blueprint("coord_pages", __name__)

@coord_pages_bp.get("/home")
@login_required
@role_required_page(["coordinator","admin"])
def coord_home_page():
    # Página para configurar horario y generar slots (ya la tienes hecha)
    return render_template("coord/home.html", title="Coordinador - Horario & Slots")

@coord_pages_bp.get("/appointments")
@login_required
@role_required_page(["coordinator","admin"])
def coord_appointments_page():
    return render_template("coord/appointments.html", title="Coordinador - Citas del día")

@coord_pages_bp.get("/drops")
@login_required
@role_required_page(["coordinator","admin"])
def coord_drops_page():
    return render_template("coord/drops.html", title="Coordinador - Drops")
