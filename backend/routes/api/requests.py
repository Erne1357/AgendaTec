# routes/api/requests.py
from datetime import date
from flask import Blueprint, request, jsonify, g
from sqlalchemy.exc import IntegrityError
from utils.decorators import api_auth_required, api_role_required
from models import db
from models.user import User
from models.program import Program
from models.program_coordinator import ProgramCoordinator
from models.time_slot import TimeSlot    # id, coordinator_id, day (DATE), start_time (TIME), is_booked
from models.request import Request
from models.appointment import Appointment

api_req_bp = Blueprint("api_requests", __name__)

# Días permitidos
ALLOWED_DAYS = {date(2025, 8, 25), date(2025, 8, 26), date(2025, 8, 27)}

def _get_current_student():
    uid = int(g.current_user["sub"])
    u = db.session.query(User).get(uid)
    return u

@api_req_bp.get("/requests/mine")
@api_auth_required
@api_role_required(["student"])
def my_requests():
    u = _get_current_student()
    active = (db.session.query(Request)
              .filter(Request.student_id == u.id, Request.status == "PENDING")
              .order_by(Request.created_at.desc())
              .first())
    history = (db.session.query(Request)
               .filter(Request.student_id == u.id, Request.status != "PENDING")
               .order_by(Request.created_at.desc())
               .limit(10).all())

    def to_dict(r: Request):
        item = {"id": r.id, "type": r.type, "status": r.status, "created_at": r.created_at.isoformat()}
        if r.type == "APPOINTMENT":
            ap = db.session.query(Appointment).filter(Appointment.request_id == r.id).first()
            if ap:
                item["appointment"] = {
                    "id": ap.id,
                    "program_id": ap.program_id,
                    "coordinator_id": ap.coordinator_id,
                    "slot_id": ap.slot_id,
                    "status": ap.status
                }
        return item

    return jsonify({
        "active": to_dict(active) if active else None,
        "history": [to_dict(x) for x in history]
    })

@api_req_bp.post("/requests")
@api_auth_required
@api_role_required(["student"])
def create_request():
    """
    Body:
      { "type": "DROP" }
      o
      { "type": "APPOINTMENT", "program_id": 1, "slot_id": 123 }
    Reglas:
      - una sola PENDING por alumno
      - slot disponible y del programa elegido
      - día del slot ∈ {2025-08-25,26,27}
    """
    u = _get_current_student()
    data = request.get_json(silent=True) or {}
    req_type = (data.get("type") or "").upper()

    exists = (db.session.query(Request.id)
              .filter(Request.student_id == u.id, Request.status == "PENDING")
              .first())
    if exists:
        return jsonify({"error": "already_has_pending"}), 409

    if req_type == "DROP":
        r = Request(student_id=u.id, type="DROP", status="PENDING")
        db.session.add(r)
        db.session.commit()
        return jsonify({"ok": True, "request_id": r.id})

    if req_type != "APPOINTMENT":
        return jsonify({"error": "invalid_type"}), 400

    try:
        program_id = int(data.get("program_id"))
        slot_id = int(data.get("slot_id"))
    except Exception:
        return jsonify({"error": "invalid_payload"}), 400

    prog = db.session.query(Program).get(program_id)
    if not prog:
        return jsonify({"error": "program_not_found"}), 404

    slot = db.session.query(TimeSlot).get(slot_id)
    if not slot or slot.is_booked:
        return jsonify({"error": "slot_unavailable"}), 409

    # Día permitido (directo desde slot.day)
    if slot.day not in ALLOWED_DAYS:
        return jsonify({"error": "day_not_allowed", "allowed": [str(x) for x in sorted(ALLOWED_DAYS)]}), 400

    # El coordinador del slot debe estar vinculado al programa
    link = (db.session.query(ProgramCoordinator)
            .filter(ProgramCoordinator.program_id == program_id,
                    ProgramCoordinator.coordinator_id == slot.coordinator_id)
            .first())
    if not link:
        return jsonify({"error": "slot_not_for_program"}), 400

    # Transacción “gana el primero”: reserva si sigue libre
    try:
        updated = (db.session.query(TimeSlot)
                   .filter(TimeSlot.id == slot_id, TimeSlot.is_booked == False)
                   .update({TimeSlot.is_booked: True}, synchronize_session=False))
        if updated != 1:
            db.session.rollback()
            return jsonify({"error": "slot_conflict"}), 409

        r = Request(student_id=u.id, program_id = data.get("program_id"), type="APPOINTMENT", status="PENDING")
        db.session.add(r)
        db.session.flush()

        ap = Appointment(
            request_id=r.id,
            student_id=u.id,
            program_id=program_id,
            coordinator_id=slot.coordinator_id,
            slot_id=slot_id,
            status="SCHEDULED"
        )
        db.session.add(ap)
        db.session.commit()
        return jsonify({"ok": True, "request_id": r.id, "appointment_id": ap.id})

    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "conflict"}), 409

@api_req_bp.patch("/requests/<int:req_id>/cancel")
@api_auth_required
@api_role_required(["student"])
def cancel_request(req_id: int):
    u = _get_current_student()
    r = (db.session.query(Request)
         .filter(Request.id == req_id, Request.student_id == u.id)
         .first())
    if not r:
        return jsonify({"error": "request_not_found"}), 404
    if r.status != "PENDING":
        return jsonify({"error": "not_pending"}), 400

    if r.type == "APPOINTMENT":
        ap = db.session.query(Appointment).filter(Appointment.request_id == r.id).first()
        if ap:
            slot = db.session.query(TimeSlot).get(ap.slot_id)
            if slot and slot.is_booked:
                slot.is_booked = False
            ap.status = "CANCELED"

    r.status = "CANCELED"
    db.session.commit()
    return jsonify({"ok": True})
