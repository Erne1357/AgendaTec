# routes/api/coord.py
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, g
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from utils.decorators import api_auth_required, api_role_required
from models import db
from models.user import User
from models.coordinator import Coordinator
from models.program import Program
from models.program_coordinator import ProgramCoordinator
from models.availability_window import AvailabilityWindow
from models.time_slot import TimeSlot
from models.request import Request
from models.appointment import Appointment

api_coord_bp = Blueprint("api_coord", __name__)

ALLOWED_DAYS = {date(2025,8,25), date(2025,8,26), date(2025,8,27)}

def _current_coordinator_id():
    try:
        uid = int(g.current_user["sub"])
    except Exception:
        return None
    u = db.session.query(User).get(uid)
    if not u:
        return None
    c = db.session.query(Coordinator).filter_by(user_id=u.id).first()
    return c.id if c else None

def _coord_program_ids(coord_id: int):
    rows = (db.session.query(ProgramCoordinator.program_id)
            .filter(ProgramCoordinator.coordinator_id == coord_id).all())
    return {r[0] for r in rows}

# ----------------- DAY CONFIG -----------------
@api_coord_bp.get("/coord/day-config")
@api_auth_required
@api_role_required(["coordinator","admin"])
def get_day_config():
    coord_id = _current_coordinator_id()
    if not coord_id:
        return jsonify({"error":"coordinator_not_found"}), 404
    day_s = (request.args.get("day") or "").strip()
    try:
        d = datetime.strptime(day_s, "%Y-%m-%d").date()
    except Exception:
        return jsonify({"error":"invalid_day_format"}), 400
    if d not in ALLOWED_DAYS:
        return jsonify({"error":"day_not_allowed","allowed":[str(x) for x in sorted(ALLOWED_DAYS)]}), 400

    wins = (db.session.query(AvailabilityWindow)
            .filter(AvailabilityWindow.coordinator_id == coord_id,
                    AvailabilityWindow.day == d)
            .order_by(AvailabilityWindow.start_time.asc())
            .all())
    items = [{"id": w.id,
              "day": str(w.day),
              "start": w.start_time.strftime("%H:%M"),
              "end": w.end_time.strftime("%H:%M"),
              "slot_minutes": w.slot_minutes} for w in wins]
    return jsonify({"day": str(d), "items": items})

@api_coord_bp.post("/coord/day-config")
@api_auth_required
@api_role_required(["coordinator","admin"])
def set_day_config():
    """
    Reemplaza la configuración de horario de UN día del coordinador:
    - Valida día permitido y que hoy < day
    - Elimina ventanas y slots NO RESERVADOS del día
    - Si hay slots reservados -> 409 con conteo
    - Crea nueva ventana y genera slots
    """
    coord_id = _current_coordinator_id()
    if not coord_id:
        return jsonify({"error":"coordinator_not_found"}), 404

    data = request.get_json(silent=True) or {}
    day_s = (data.get("day") or "").strip()
    start_s = (data.get("start") or "").strip()
    end_s   = (data.get("end") or "").strip()
    slot_minutes = int(data.get("slot_minutes", 10))

    try:
        d = datetime.strptime(day_s, "%Y-%m-%d").date()
    except Exception:
        return jsonify({"error":"invalid_day_format"}), 400
    if d not in ALLOWED_DAYS:
        return jsonify({"error":"day_not_allowed","allowed":[str(x) for x in sorted(ALLOWED_DAYS)]}), 400

    today = date.today()
    if today >= d:
        return jsonify({"error":"cannot_modify_today_or_past"}), 400

    try:
        sh, sm = map(int, start_s.split(":"))
        eh, em = map(int, end_s.split(":"))
        start_t = datetime.strptime(f"{sh:02d}:{sm:02d}", "%H:%M").time()
        end_t   = datetime.strptime(f"{eh:02d}:{em:02d}", "%H:%M").time()
    except Exception:
        return jsonify({"error":"invalid_time_format"}), 400

    if (end_t <= start_t) or (slot_minutes not in (5,10,15,20,30,60)):
        return jsonify({"error":"invalid_time_range_or_slot_size"}), 400

    # ¿hay slots reservados ese día?
    booked_cnt = (db.session.query(TimeSlot.id)
                  .filter(TimeSlot.coordinator_id == coord_id,
                          TimeSlot.day == d,
                          TimeSlot.is_booked == True)
                  .count())
    if booked_cnt > 0:
        return jsonify({"error":"booked_slots_exist","booked_count": booked_cnt}), 409

    # Borrar ventanas del día + slots no reservados
    wins_deleted = (db.session.query(AvailabilityWindow)
                    .filter(AvailabilityWindow.coordinator_id == coord_id,
                            AvailabilityWindow.day == d)
                    .delete(synchronize_session=False))

    slots_deleted = (db.session.query(TimeSlot)
                     .filter(TimeSlot.coordinator_id == coord_id,
                             TimeSlot.day == d,
                             TimeSlot.is_booked == False)
                     .delete(synchronize_session=False))

    # Crear ventana nueva
    av = AvailabilityWindow(
        coordinator_id = coord_id,
        day            = d,
        start_time     = start_t,
        end_time       = end_t,
        slot_minutes   = slot_minutes
    )
    db.session.add(av)
    db.session.flush()

    # Generar slots
    created = 0
    step = timedelta(minutes=slot_minutes)
    cur_dt = datetime.combine(d, start_t)
    end_dt = datetime.combine(d, end_t)
    while (cur_dt + step) <= end_dt:
        db.session.add(TimeSlot(
            coordinator_id = coord_id,
            day            = d,
            start_time     = cur_dt.time(),
            end_time       = (cur_dt + step).time(),
            is_booked      = False
        ))
        created += 1
        cur_dt += step

    db.session.commit()
    return jsonify({"ok": True,
                    "windows_deleted": wins_deleted,
                    "slots_deleted": slots_deleted,
                    "slots_created": created})

# ----------------- APPOINTMENTS LIST -----------------
@api_coord_bp.get("/coord/appointments")
@api_auth_required
@api_role_required(["coordinator","admin"])
def coord_appointments():
    coord_id = _current_coordinator_id()
    if not coord_id:
        return jsonify({"error":"coordinator_not_found"}), 404

    day_s = (request.args.get("day") or "").strip()
    status = (request.args.get("status") or "").strip().upper()
    program_id = request.args.get("program_id")
    q = (request.args.get("q") or "").strip()
    page = int(request.args.get("page", 1))
    page_size = min(max(int(request.args.get("page_size", 20)), 1), 100)

    try:
        d = datetime.strptime(day_s, "%Y-%m-%d").date()
    except Exception:
        return jsonify({"error":"invalid_day_format"}), 400
    if d not in ALLOWED_DAYS:
        return jsonify({"error":"day_not_allowed"}), 400

    query = (db.session.query(Appointment, TimeSlot, Program, Request)
             .join(TimeSlot, TimeSlot.id == Appointment.slot_id)
             .join(Program, Program.id == Appointment.program_id)
             .join(Request, Request.id == Appointment.request_id)
             .filter(Appointment.coordinator_id == coord_id,
                     TimeSlot.day == d))

    if status:
        query = query.filter(Appointment.status == status)
    if program_id:
        try:
            pid = int(program_id)
        except:
            return jsonify({"error":"invalid_program_id"}), 400
        # Scope: sólo programas del coordinador
        if pid not in _coord_program_ids(coord_id):
            return jsonify({"error":"forbidden_program"}), 403
        query = query.filter(Appointment.program_id == pid)
    if q:
        # Búsqueda simple por nombre o control_number (si está en Request -> User join opcional)
        # Para mantenerlo simple aquí, omitimos el join a User; puedes extenderlo luego.
        pass

    total = query.count()
    rows = (query
            .order_by(TimeSlot.start_time.asc())
            .offset((page-1)*page_size).limit(page_size)
            .all())

    items = []
    for ap, slot, prog, req in rows:
        items.append({
            "appointment_id": ap.id,
            "request_id": req.id,
            "program": {"id": prog.id, "name": prog.name},
            "slot": {
                "day": str(slot.day),
                "start_time": slot.start_time.strftime("%H:%M"),
                "end_time": slot.end_time.strftime("%H:%M")
            },
            "status": ap.status
        })
    return jsonify({"day": str(d), "total": total, "items": items})

# ----------------- APPOINTMENT STATUS UPDATE -----------------
@api_coord_bp.patch("/coord/appointments/<int:ap_id>")
@api_auth_required
@api_role_required(["coordinator","admin"])
def update_appointment(ap_id: int):
    coord_id = _current_coordinator_id()
    if not coord_id:
        return jsonify({"error":"coordinator_not_found"}), 404
    ap = db.session.query(Appointment).get(ap_id)
    if not ap or ap.coordinator_id != coord_id:
        return jsonify({"error":"appointment_not_found"}), 404

    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").upper()
    if new_status not in {"SCHEDULED","DONE","NO_SHOW","CANCELED"}:
        return jsonify({"error":"invalid_status"}), 400

    # sincronizar Request.status
    req = db.session.query(Request).get(ap.request_id)
    if not req:
        return jsonify({"error":"request_not_found"}), 404

    # transición
    if new_status == "SCHEDULED":
        req.status = "PENDING"
    elif new_status == "DONE":
        req.status = "RESOLVED_SUCCESS"
    elif new_status == "NO_SHOW":
        req.status = "NO_SHOW"
    elif new_status == "CANCELED":
        req.status = "CANCELED"
        # liberar slot
        slot = db.session.query(TimeSlot).get(ap.time_slot_id)
        if slot and slot.is_booked:
            slot.is_booked = False

    ap.status = new_status
    db.session.commit()
    return jsonify({"ok": True})

# ----------------- DROPS -----------------
@api_coord_bp.get("/coord/drops")
@api_auth_required
@api_role_required(["coordinator","admin"])
def coord_drops():
    coord_id = _current_coordinator_id()
    if not coord_id:
        return jsonify({"error":"coordinator_not_found"}), 404

    status = (request.args.get("status") or "PENDING").upper()
    program_id = request.args.get("program_id")
    page = int(request.args.get("page", 1))
    page_size = min(max(int(request.args.get("page_size", 20)), 1), 100)

    q = (db.session.query(Request)
         .filter(Request.type == "DROP"))

    if status:
        q = q.filter(Request.status == status)

    if program_id:
        try:
            pid = int(program_id)
        except:
            return jsonify({"error":"invalid_program_id"}), 400
        # scope por programas del coordinador
        if pid not in _coord_program_ids(coord_id):
            return jsonify({"error":"forbidden_program"}), 403
        q = q.filter(Request.program_id == pid)  # si requests guarda program_id; si no, omite este filtro

    total = q.count()
    rows = (q.order_by(Request.created_at.desc())
              .offset((page-1)*page_size).limit(page_size).all())

    items = [{"id": r.id, "status": r.status, "created_at": r.created_at.isoformat()}
             for r in rows]
    return jsonify({"total": total, "items": items})

@api_coord_bp.patch("/coord/requests/<int:req_id>/status")
@api_auth_required
@api_role_required(["coordinator","admin"])
def update_request_status(req_id: int):
    coord_id = _current_coordinator_id()
    if not coord_id:
        return jsonify({"error":"coordinator_not_found"}), 404

    r = db.session.query(Request).get(req_id)
    if not r or r.type != "DROP":
        return jsonify({"error":"request_not_found_or_not_drop"}), 404

    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").upper()
    allowed = {"RESOLVED_SUCCESS","RESOLVED_NOT_COMPLETED","NO_SHOW","ATTENDED_OTHER_SLOT","CANCELED"}
    if new_status not in allowed:
        return jsonify({"error":"invalid_status"}), 400

    r.status = new_status
    db.session.commit()
    return jsonify({"ok": True})
