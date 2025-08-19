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
from utils.security import verify_nip, hash_nip

api_coord_bp = Blueprint("api_coord", __name__)

ALLOWED_DAYS = {date(2025,8,25), date(2025,8,26), date(2025,8,27)}
DEFAULT_NIP = "1234"

def _current_user():
    try:
        uid = int(g.current_user["sub"])
    except Exception:
        return None
    u = db.session.query(User).get(uid)
    return u

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
    Agrega/actualiza una ventana de disponibilidad para UN día:
    - Valida día permitido y que hoy < day
    - No borra todo el día: solo elimina ventanas/slots que SE SOLAPAN con la nueva
    - Si en el rango solapado hay slots reservados -> 409 con conteo
    - Crea la ventana y genera slots para su rango
    """
    coord_id = _current_coordinator_id()
    if not coord_id:
        return jsonify({"error":"coordinator_not_found"}), 404

    data = request.get_json(silent=True) or {}
    day_s = (data.get("day") or "").strip()
    start_s = (data.get("start") or "").strip()
    end_s   = (data.get("end") or "").strip()
    slot_minutes = int(data.get("slot_minutes", 10))

    # --- Validaciones de fecha/hora ---
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

    # Atajos para filtros por hora
    # (comparaciones con columnas TIME en SQLAlchemy)
    time_ge = start_t
    time_lt = end_t

    # --- Ver si hay RESERVAS en el rango que vamos a tocar ---
    # Solo contamos reservas que realmente caen dentro [start_t, end_t)
    overlap_booked_cnt = (
        db.session.query(TimeSlot.id)
        .filter(TimeSlot.coordinator_id == coord_id,
                TimeSlot.day == d,
                TimeSlot.start_time >= time_ge,
                TimeSlot.start_time <  time_lt,
                TimeSlot.is_booked == True)
        .count()
    )
    if overlap_booked_cnt > 0:
        return jsonify({
            "error": "overlap_booked_slots_exist",
            "booked_count": overlap_booked_cnt
        }), 409

    # --- Identificar ventanas que se SOLAPAN con la nueva ---
    # Overlap si: NOT (existing.end <= start OR existing.start >= end)
    overlapping_windows = (
        db.session.query(AvailabilityWindow)
        .filter(AvailabilityWindow.coordinator_id == coord_id,
                AvailabilityWindow.day == d,
                ~(
                    (AvailabilityWindow.end_time   <= time_ge) |
                    (AvailabilityWindow.start_time >= time_lt)
                ))
        .all()
    )

    # --- Borrar SOLO slots no reservados dentro del rango nuevo ---
    slots_deleted = (
        db.session.query(TimeSlot)
        .filter(TimeSlot.coordinator_id == coord_id,
                TimeSlot.day == d,
                TimeSlot.start_time >= time_ge,
                TimeSlot.start_time <  time_lt,
                TimeSlot.is_booked == False)
        .delete(synchronize_session=False)
    )

    # --- Borrar ventanas que solapan (ya que vamos a sustituir ese tramo) ---
    # OJO: solo borramos las ventanas completas que se solapan; si quisieras "recortar"
    # ventanas en lugar de borrarlas, habría que partirlas (no requerido ahora).
    wins_deleted = 0
    for w in overlapping_windows:
        db.session.delete(w)
        wins_deleted += 1

    # --- Crear la nueva ventana ---
    av = AvailabilityWindow(
        coordinator_id = coord_id,
        day            = d,
        start_time     = start_t,
        end_time       = end_t,
        slot_minutes   = slot_minutes
    )
    db.session.add(av)
    db.session.flush()

    # --- Generar slots solo para el rango de esta ventana ---
    created = 0
    step = timedelta(minutes=slot_minutes)
    cur_dt = datetime.combine(d, start_t)
    end_dt = datetime.combine(d, end_t)
    while (cur_dt + step) <= end_dt:
        # En caso de un índice único (coordinator_id, day, start_time),
        # este INSERT fallaría si ya existiera el slot; pero como ya
        # borramos solapados, no debería chocar.
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
    return jsonify({
        "ok": True,
        "windows_deleted": wins_deleted,
        "slots_deleted": slots_deleted,
        "slots_created": created
    })


# ----------------- APPOINTMENTS LIST -----------------
@api_coord_bp.get("/coord/appointments")
@api_auth_required
@api_role_required(["coordinator","admin"])
def coord_appointments():
    coord_id = _current_coordinator_id()
    if not coord_id:
        return jsonify({"error":"coordinator_not_found"}), 404

    day_s = (request.args.get("day") or "").strip()
    req_status = (request.args.get("req_status") or "").strip().upper()
    include_empty = (request.args.get("include_empty") or "0") in ("1","true","True")
    request_id = request.args.get("request_id")  # para modal/consulta puntual
    program_id = request.args.get("program_id")
    page = int(request.args.get("page", 1))
    page_size = min(max(int(request.args.get("page_size", 200 if include_empty else 50)), 1), 500)

    try:
        d = datetime.strptime(day_s, "%Y-%m-%d").date()
    except Exception:
        return jsonify({"error":"invalid_day_format"}), 400
    if d not in ALLOWED_DAYS:
        return jsonify({"error":"day_not_allowed"}), 400

    # Para vista lista (solo con citas existentes)
    base = (db.session.query(Appointment, TimeSlot, Program, Request, User)
            .join(TimeSlot, TimeSlot.id == Appointment.slot_id)
            .join(Program, Program.id == Appointment.program_id)
            .join(Request, Request.id == Appointment.request_id)
            .join(User, User.id == Appointment.student_id)
            .filter(Appointment.coordinator_id == coord_id,
                    TimeSlot.day == d))

    if req_status:
        base = base.filter(Request.status == req_status)
    if program_id:
        try:
            pid = int(program_id)
        except:
            return jsonify({"error":"invalid_program_id"}), 400
        if pid not in _coord_program_ids(coord_id):
            return jsonify({"error":"forbidden_program"}), 403
        base = base.filter(Appointment.program_id == pid)
    if request_id:
        try:
            rid = int(request_id)
            base = base.filter(Request.id == rid)
        except:
            return jsonify({"error":"invalid_request_id"}), 400

    total = base.count()
    rows = (base.order_by(TimeSlot.start_time.asc())
                 .offset((page-1)*page_size).limit(page_size).all())

    items = []
    for ap, slot, prog, req, stu in rows:
        items.append({
            "appointment_id": ap.id,
            "request_id": req.id,
            "program": {"id": prog.id, "name": prog.name},
            "description": req.description,
            "student": {"id": stu.id, "full_name": stu.full_name, "control_number": stu.control_number},
            "slot": {"day": str(slot.day),
                     "start_time": slot.start_time.strftime("%H:%M"),
                     "end_time": slot.end_time.strftime("%H:%M")},
            "request_status": req.status
        })

    if not include_empty:
        return jsonify({"day": str(d), "total": total, "items": items})

    # Vista tabla: devolver TODOS los slots del coordinador en ese día (con o sin cita)
    # Left join: time_slots LEFT JOIN appointments (del coordinador y día)
    ts_q = (db.session.query(TimeSlot)
            .filter(TimeSlot.coordinator_id == coord_id, TimeSlot.day == d)
            .order_by(TimeSlot.start_time.asc()))
    slots = []
    # Para mapear rápido appointment por slot_id
    ap_by_slot = {}
    for ap, slot, prog, req, stu in rows:
        ap_by_slot[slot.id] = {
            "request_id": req.id,
            "program": {"id": prog.id, "name": prog.name},
            "description": req.description,
            "student": {"id": stu.id, "full_name": stu.full_name, "control_number": stu.control_number},
            "request_status": req.status
        }
    for s in ts_q.all():
        entry = {
            "slot_id": s.id,
            "start": datetime.combine(s.day, s.start_time).strftime("%H:%M"),
            "end": datetime.combine(s.day, s.end_time).strftime("%H:%M"),
            "appointment": ap_by_slot.get(s.id)  # puede ser None si está libre
        }
        slots.append(entry)

    return jsonify({"day": str(d), "slots": slots})

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
        slot = db.session.query(TimeSlot).get(ap.slot_id)
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

    status = (request.args.get("status") or "ALL").upper()
    program_id = request.args.get("program_id")
    request_id = request.args.get("request_id")  # <-- NUEVO
    page = int(request.args.get("page", 1))
    page_size = min(max(int(request.args.get("page_size", 20)), 1), 100)

    q = (db.session.query(Request, User)
         .join(User, User.id == Request.student_id)
         .filter(Request.type == "DROP"))

    if request_id:
        try:
            rid = int(request_id)
        except:
            return jsonify({"error":"invalid_request_id"}), 400
        q = q.filter(Request.id == rid)

    if status != "ALL":
        q = q.filter(Request.status == status)

    if program_id:
        try:
            pid = int(program_id)
        except:
            return jsonify({"error":"invalid_program_id"}), 400
        if pid not in _coord_program_ids(coord_id):
            return jsonify({"error":"forbidden_program"}), 403
        q = q.filter(Request.program_id == pid)

    # Orden: FIFO para PENDING; si "ALL", primero pendientes en FIFO, luego el resto
    from sqlalchemy import case
    if status == "PENDING":
        q = q.order_by(Request.created_at.asc(), Request.id.asc())
    elif status == "ALL":
        q = q.order_by(
            case((Request.status == "PENDING", 0), else_=1),
            Request.created_at.asc(),
            Request.id.asc()
        )
    else:
        q = q.order_by(Request.created_at.asc(), Request.id.asc())

    total = q.count()
    rows = (q.offset((page-1)*page_size).limit(page_size).all())

    items = [{
        "id": r.id,
        "status": r.status,
        "description": r.description,
        "created_at": r.created_at.isoformat(),
        "student": {"id": u.id, "full_name": u.full_name, "control_number": u.control_number}
    } for r, u in rows]

    return jsonify({"total": total, "items": items})

@api_coord_bp.patch("/coord/requests/<int:req_id>/status")
@api_auth_required
@api_role_required(["coordinator","admin"])
def update_request_status(req_id: int):
    coord_id = _current_coordinator_id()
    if not coord_id:
        return jsonify({"error":"coordinator_not_found"}), 404

    r = db.session.query(Request).get(req_id)
    if not r:
        return jsonify({"error":"request_not_found"}), 404

    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").upper()
    allowed = {"RESOLVED_SUCCESS","RESOLVED_NOT_COMPLETED","NO_SHOW","ATTENDED_OTHER_SLOT","CANCELED"}
    if new_status not in allowed:
        return jsonify({"error":"invalid_status"}), 400

    # Solo permitir que el coordinador cambie requests asociados a sus programas (si aplica)
    # Nota: si necesitas forzar scope, valida con ProgramCoordinator.
    # if r.program_id not in _coord_program_ids(coord_id):
    #     return jsonify({"error":"forbidden_program"}), 403

    # Actualizar estado de la solicitud
    r.status = new_status

    # Si es APPOINTMENT, reflejar en Appointment.status y liberar slot cuando aplique
    if r.type == "APPOINTMENT":
        ap = db.session.query(Appointment).filter(Appointment.request_id == r.id,
                                                  Appointment.coordinator_id == coord_id).first()
        if ap:
            if new_status in ("RESOLVED_SUCCESS", "RESOLVED_NOT_COMPLETED", "ATTENDED_OTHER_SLOT"):
                ap.status = "DONE"
            elif new_status == "NO_SHOW":
                ap.status = "NO_SHOW"
            elif new_status == "CANCELED":
                ap.status = "CANCELED"
                slot = db.session.query(TimeSlot).get(ap.slot_id)
                if slot and slot.is_booked:
                    slot.is_booked = False

    db.session.commit()
    return jsonify({"ok": True})

@api_coord_bp.get("/coord/password-state")
@api_auth_required
@api_role_required(["coordinator","admin"])
def coord_password_state():
    u = _current_user()
    if not u:
        return jsonify({"error":"user_not_found"}), 404
    must_change = verify_nip(DEFAULT_NIP, u.nip_hash )
    return jsonify({"must_change": must_change})

@api_coord_bp.post("/coord/change_password")
@api_auth_required
@api_role_required(["coordinator","admin"])
def change_password():
    """
    Cambia el NIP (4 dígitos). Se hashea en servidor.
    Si el usuario sigue con 1234, no exigimos current_password.
    Si NO está en 1234, opcionalmente puedes exigir current_password (comentado).
    """
    u = _current_user()
    if not u:
        return jsonify({"error":"user_not_found"}), 404

    data = request.get_json(silent=True) or {}
    new_password = (data.get("new_password") or "").strip()

    if not (new_password.isdigit() and len(new_password) == 4):
        return jsonify({"error":"invalid_new_password"}), 400

    # Guardar hash nuevo
    coord = db.session.query(Coordinator).filter_by(user_id=u.id).first()
    coord.must_change_pw = False 
    u.nip_hash = hash_nip(new_password)
    db.session.commit()
    return jsonify({"ok": True})
