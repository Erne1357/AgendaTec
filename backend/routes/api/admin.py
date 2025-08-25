# backend/routes/api/admin.py
from __future__ import annotations
from datetime import datetime, timedelta, date
from typing import Optional, Iterable

from flask import Blueprint, request, jsonify, send_file, g, current_app
from sqlalchemy import func, case, and_, or_, cast, Date
from sqlalchemy.orm import joinedload, contains_eager

from models import db
from models.user import User
from models.role import Role
from models.coordinator import Coordinator
from models.program import Program
from models.program_coordinator import ProgramCoordinator
from models.request import Request as Req
from models.appointment import Appointment
from models.time_slot import TimeSlot
from models.notification import Notification
from models.audit_log import AuditLog

from utils.decorators import api_auth_required, api_role_required
from utils.jwt_tools import encode_jwt
from utils.security import hash_nip  # si ya tienes util p/ NIP hash (ajusta si difiere)
from utils.notify import create_notification as notify_user  # si ya tienes un helper (ajusta si difiere)
import logging
from xlsxwriter import Workbook
# XLSX
from io import BytesIO

import pandas as pd

api_admin_bp = Blueprint("api_admin", __name__)

# ---------- Helpers ----------

def _parse_dt(s: Optional[str], default: Optional[datetime] = None) -> datetime:
    if s:
        # admite 'YYYY-MM-DD' o ISO completo
        try:
            if len(s) == 10:
                return datetime.fromisoformat(s)
            return datetime.fromisoformat(s)
        except ValueError:
            pass
    return default or datetime.utcnow()

def _range_from_query() -> tuple[datetime, datetime]:
    qf = request.args.get("from")
    qt = request.args.get("to")
    end = _parse_dt(qt, datetime.utcnow())
    start = _parse_dt(qf, end - timedelta(days=7))
    # normaliza para incluir el día 'to' completo si vino solo fecha
    if qf and len(qf) == 10:
        start = datetime.combine(start.date(), datetime.min.time())
    if qt and len(qt) == 10:
        end = datetime.combine(end.date(), datetime.max.time())
    return start, end

def _paginate(query, default_limit=20, max_limit=100):
    try:
        limit = min(int(request.args.get("limit", default_limit)), max_limit)
    except ValueError:
        limit = default_limit
    try:
        offset = int(request.args.get("offset", 0))
    except ValueError:
        offset = 0
    total = query.order_by(None).count()
    items = query.limit(limit).offset(offset).all()
    return items, total

def _ensure_admin():
    # por si necesitas usar fuera de decoradores
    u = getattr(g, "current_user", None)
    if not u or u.get("role") != "admin":
        from flask import abort
        abort(403)

# ---------- Stats Overview ----------

@api_admin_bp.get("/stats/overview")
@api_auth_required
@api_role_required(["admin"])
def stats_overview():
    start, end = _range_from_query()

    # Totales por estado (Requests)
    totals_q = (
        db.session.query(Req.status, func.count(Req.id))
        .filter(Req.created_at >= start, Req.created_at <= end)
        .group_by(Req.status)
    )
    totals = [{"status": s, "total": t} for (s, t) in totals_q.all()]

    # Serie diaria de solicitudes (últimos N días del rango)
    # Postgres: date_trunc('day', ...). Portátil: cast(Req.created_at, Date)
    daily_q = (
        db.session.query(cast(Req.created_at, Date).label("day"), func.count(Req.id))
        .filter(Req.created_at >= start, Req.created_at <= end)
        .group_by(cast(Req.created_at, Date))
        .order_by(cast(Req.created_at, Date))
    )
    series = [{"day": d.isoformat(), "total": n} for (d, n) in daily_q.all()]

    # No-show rate (Appointments): NO_SHOW / (DONE + NO_SHOW)
    denom_q = (
        db.session.query(func.count(Appointment.id))
        .join(Req, Req.id == Appointment.request_id)
        .filter(
            Req.type == "APPOINTMENT",
            Req.created_at >= start,
            Req.created_at <= end,
            Appointment.status.in_(["DONE", "NO_SHOW"]),
        )
    )
    denom = denom_q.scalar() or 0
    noshow_q = (
        db.session.query(func.count(Appointment.id))
        .join(Req, Req.id == Appointment.request_id)
        .filter(
            Req.type == "APPOINTMENT",
            Req.created_at >= start,
            Req.created_at <= end,
            Appointment.status == "NO_SHOW",
        )
    )
    noshows = noshow_q.scalar() or 0
    no_show_rate = (noshows / denom) if denom else 0.0

    # Pendientes por coordinador
    pending_by_coord_q = (
        db.session.query(
            Coordinator.id.label("coordinator_id"),
            User.full_name.label("coordinator_name"),
            func.count(Req.id).label("pending"),
        )
        .join(User, User.id == Coordinator.user_id)
        .join(Appointment, Appointment.coordinator_id == Coordinator.id)
        .join(Req, Req.id == Appointment.request_id)
        .filter(Req.status == "PENDING")
        .group_by(Coordinator.id, User.full_name)
        .order_by(func.count(Req.id).desc())
    )
    #current_app.logger.warning("Primero : ", pending_by_coord)
    pending_by_coord = [
        dict(coordinator_id=i, coordinator_name=n, pending=p)
        for (i, n, p) in pending_by_coord_q.all()
    ]
    #current_app.logger.warning("segundo : " , pending_by_coord)

    return jsonify(
        {
            "totals": totals,
            "series": series,
            "no_show_rate": no_show_rate,
            "pending_by_coordinator": pending_by_coord,
        }
    )

# ---------- Listado y edición de solicitudes ----------

@api_admin_bp.get("/requests")
@api_auth_required
@api_role_required(["admin"])
def admin_list_requests():
    start, end = _range_from_query()
    status = request.args.get("status")
    program_id = request.args.get("program_id", type=int)
    coordinator_id = request.args.get("coordinator_id", type=int)
    q = request.args.get("q", "").strip()

    qry = (
        db.session.query(Req)
        .options(
            joinedload(Req.appointment).joinedload(Appointment.coordinator).joinedload(Coordinator.user),
            joinedload(Req.program),
            joinedload(Req.student),
        )
        .filter(Req.created_at >= start, Req.created_at <= end)
    )
    if status:
        qry = qry.filter(Req.status == status)
    if program_id:
        qry = qry.filter(Req.program_id == program_id)
    if coordinator_id:
        # a través de Appointment
        qry = qry.join(Appointment, Appointment.request_id == Req.id).filter(
            Appointment.coordinator_id == coordinator_id
        )
    if q:
        # busca por no. de control o nombre del alumno
        qry = qry.join(User, User.id == Req.student_id).filter(
            or_(User.control_number.ilike(f"%{q}%"),User.username.ilike(f"%{q}%"), User.full_name.ilike(f"%{q}%"))
        )

    items, total = _paginate(qry.order_by(Req.created_at.desc()))

    def _to_dict(r: Req):
        a: Optional[Appointment] = r.appointment
        coord_name = a.coordinator.user.full_name if a and a.coordinator and a.coordinator.user else None
        return {
            "id": r.id,
            "type": r.type,
            "status": r.status,
            "program": r.program.name if r.program else None,
            "student": r.student.full_name if r.student else None,
            "student_control_number": r.student.control_number if r.student.control_number else r.student.username,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "appointment": {
                "id": a.id,
                "status": a.status,
                "coordinator_id": a.coordinator_id,
                "coordinator_name": coord_name,
                "time_slot_id": a.slot_id,
            } if a else None,
        }

    return jsonify({"items": [_to_dict(x) for x in items], "total": total})

@api_admin_bp.patch("/requests/<int:req_id>/status")
@api_auth_required
@api_role_required(["admin"])
def admin_change_request_status(req_id: int):
    data = request.get_json(silent=True) or {}
    new_status: str = data.get("status")
    reason: str = data.get("reason", "")
    actor_id = int((g.current_user or {}).get("sub")) if getattr(g,"current_user",None) else None
    resp, code = admin_change_request_status(actor_user_id=actor_id, req_id=req_id, new_status=new_status, reason=reason)
    return jsonify(resp), code

# ---------- Coordinadores: crear/actualizar ----------

@api_admin_bp.post("/users/coordinators")
@api_auth_required
@api_role_required(["admin"])
def create_coordinator():
    data = request.get_json(silent=True) or {}
    name: str = data.get("name", "").strip()
    email: str = data.get("email", "").strip()
    control_number: Optional[str] = data.get("control_number")
    username: str = data.get("username","").strip() # opcional para staff
    program_ids: list[int] = data.get("program_ids", [])
    nip: str = data.get("nip", "1234")  # NIP temporal

    if not name:
        return jsonify({"error": "missing_name"}), 400

    # Rol coordinator
    role = db.session.query(Role).filter_by(name="coordinator").first()
    if not role:
        return jsonify({"error": "role_not_found"}), 500

    # User
    u = User(full_name=name, email=email or None, control_number=control_number, username = username, role_id=role.id, nip_hash=hash_nip(nip))
    db.session.add(u)
    db.session.flush()

    # Coordinator
    c = Coordinator(user_id=u.id, contact_email=email or None)
    db.session.add(c)
    db.session.flush()

    # Asignaciones
    if program_ids:
        # valida que existan
        valid_programs = db.session.query(Program.id).filter(Program.id.in_(program_ids)).all()
        valid_ids = [pid for (pid,) in valid_programs]
        for pid in valid_ids:
            db.session.add(ProgramCoordinator(program_id=pid, coordinator_id=c.id))

    # Audit
    actor_id = g.current_user.get("sub") if getattr(g, "current_user", None) else None
    db.session.add(
        AuditLog(
            actor_id=actor_id,
            entity="coordinator",
            entity_id=c.id,
            action="create",
            payload_json=None,
        )
    )
    db.session.commit()

    return jsonify({"id": c.id, "user_id": u.id})

@api_admin_bp.patch("/users/coordinators/<int:coord_id>")
@api_auth_required
@api_role_required(["admin"])
def update_coordinator(coord_id: int):
    data = request.get_json(silent=True) or {}
    name: Optional[str] = data.get("name")
    email: Optional[str] = data.get("email")
    program_ids: Optional[list[int]] = data.get("program_ids")

    c = db.session.query(Coordinator).options(joinedload(Coordinator.user)).filter(Coordinator.id == coord_id).first()
    if not c:
        return jsonify({"error": "not_found"}), 404

    before = {"name": c.user.full_name, "email": c.contact_email}

    if name is not None:
        c.user.full_name = name.strip() or c.user.full_name
    if email is not None:
        c.contact_email = email.strip() or None

    if program_ids is not None:
        # reemplaza asignaciones
        db.session.query(ProgramCoordinator).filter(ProgramCoordinator.coordinator_id == c.id).delete()
        if program_ids:
            valid_programs = db.session.query(Program.id).filter(Program.id.in_(program_ids)).all()
            valid_ids = [pid for (pid,) in valid_programs]
            for pid in valid_ids:
                db.session.add(ProgramCoordinator(program_id=pid, coordinator_id=c.id))

    after = {"name": c.user.full_name, "email": c.contact_email, "program_ids": program_ids}
    actor_id = g.current_user.get("sub") if getattr(g, "current_user", None) else None
    db.session.add(
        AuditLog(
            actor_user_id=actor_id,
            entity="coordinator",
            entity_id=c.id,
            action="update",
            from_json=before,
            to_json=after,
        )
    )
    db.session.commit()
    return jsonify({"ok": True})


# backend/routes/api/admin.py (agrega esto)

@api_admin_bp.get("/users/coordinators")
@api_auth_required
@api_role_required(["admin"])
def list_coordinators():
    """
    Lista coordinadores con sus programas (para usar en Admin · Usuarios y combos).
    Filtros opcionales: q (texto), program_id (int).
    """
    from sqlalchemy.orm import joinedload
    from models.coordinator import Coordinator
    from models.program_coordinator import ProgramCoordinator
    from models.program import Program
    from models.user import User

    q = (request.args.get("q") or "").strip().lower()
    program_id = request.args.get("program_id", type=int)

    base = (
        db.session.query(Coordinator)
        .options(joinedload(Coordinator.user))
    )
    if q:
        base = base.join(User).filter(
            (User.full_name.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%"))
        )
    rows = base.all()

    # programas por coord
    prog_map = {}
    if rows:
        coord_ids = [c.id for c in rows]
        links = (db.session.query(ProgramCoordinator.coordinator_id, Program.id, Program.name)
                 .join(Program, Program.id == ProgramCoordinator.program_id)
                 .filter(ProgramCoordinator.coordinator_id.in_(coord_ids))
                 .all())
        for cid, pid, pname in links:
            prog_map.setdefault(cid, []).append({"id": pid, "name": pname})

    items = []
    for c in rows:
        progs = prog_map.get(c.id, [])
        if program_id and all(p["id"] != program_id for p in progs):
            continue
        items.append({
            "id": c.id,
            "user_id": c.user_id,
            "name": c.user.full_name,
            "email": c.contact_email,
            "programs": progs,
        })

    return jsonify({"items": items})

# ---------- Reporte XLSX ----------

@api_admin_bp.post("/reports/requests.xlsx")
@api_auth_required
@api_role_required(["admin"])
def export_requests_xlsx():
    start, end = _range_from_query()
    status = request.args.get("status")
    program_id = request.args.get("program_id", type=int)
    coordinator_id = request.args.get("coordinator_id", type=int)
    q = request.args.get("q", "").strip()

    qry = (
        db.session.query(Req)
        .options(
            joinedload(Req.appointment).joinedload(Appointment.coordinator).joinedload(Coordinator.user),
            joinedload(Req.program),
            joinedload(Req.student),
        )
        .filter(Req.created_at >= start, Req.created_at <= end)
        .order_by(Req.created_at.desc())
    )
    if status:
        qry = qry.filter(Req.status == status)
    if program_id:
        qry = qry.filter(Req.program_id == program_id)
    if coordinator_id:
        qry = qry.join(Appointment, Appointment.request_id == Req.id).filter(
            Appointment.coordinator_id == coordinator_id
        )
    if q:
        qry = qry.join(User, User.id == Req.student_id).filter(
            or_(User.control_number.ilike(f"%{q}%"), User.full_name.ilike(f"%{q}%"))
        )

    rows = []
    for r in qry.all():
        a = r.appointment
        rows.append(
            {
                "ID": r.id,
                "Tipo": r.type,
                "Estado": r.status,
                "Programa": r.program.name if r.program else None,
                "Alumno": r.student.full_name if r.student else None,
                "NoControl": r.student.control_number if r.student else None,
                "Coord": (a.coordinator.user.full_name if a and a.coordinator and a.coordinator.user else None),
                "CitaID": a.id if a else None,
                "CitaStatus": a.status if a else None,
                "Creado": r.created_at.isoformat() if r.created_at else None,
                "Actualizado": r.updated_at.isoformat() if r.updated_at else None,
            }
        )

    df = pd.DataFrame(rows)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Solicitudes")
    buf.seek(0)
    filename = f"solicitudes_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )
