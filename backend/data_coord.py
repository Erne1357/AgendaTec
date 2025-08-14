# data_coord.py (colócalo en la carpeta raíz)
import os
from datetime import datetime, date, time, timedelta

from app import create_app
from models import db
from models.role import Role
from models.user import User
# Ajusta estos imports a tus nombres reales de modelos:
from models.program import Program
from models.coordinator import Coordinator
from models.program_coordinator import ProgramCoordinator
from models.availability_window import AvailabilityWindow
from models.time_slot import TimeSlot

from utils.security import hash_nip

PROGRAMS = [
    "Ingeniería en Sistemas Computacionales",
    "Ingeniería Industrial",
    "Ingeniería Electromecánica",
    "Ingeniería en Gestión Empresarial",
    "Ingeniería Mecatrónica",
]

COORDINATORS = [
    # (full_name, email, nip, office_hours_display)
    ("Mtra. Laura Ramírez", "laura.ramirez@itcj.edu.mx", "1234", "L–V 09:00–13:00"),
    ("Mtro. Carlos Pérez",  "carlos.perez@itcj.edu.mx",  "1234", "L–V 09:00–13:00"),
]

SOCIAL_SERVICE = ("Servicio Social ITCJ", "servicio.social@itcj.edu.mx", "1234")

# 25–27 agosto, 09:00–13:00, slots de 10 min (según tu plan)
DAYS = [date(2025, 8, 25), date(2025, 8, 26), date(2025, 8, 27)]
START = time(9, 0)
END = time(13, 0)
SLOT_MINUTES = 10

def daterange(start_dt: datetime, end_dt: datetime, step_minutes: int):
    cur = start_dt
    while cur < end_dt:
        yield cur
        cur += timedelta(minutes=step_minutes)

def main():
    app = create_app()
    with app.app_context():
        # Roles mínimos
        role_names = ["student", "social_service", "coordinator", "admin"]
        roles = {r.name: r for r in db.session.query(Role).filter(Role.name.in_(role_names)).all()}
        for rn in role_names:
            if rn not in roles:
                nr = Role(name=rn)
                db.session.add(nr)
                db.session.flush()
                roles[rn] = nr

        # Programas
        try:
            from models.program import Program
            existing = {p.name for p in db.session.query(Program).all()}
            for name in PROGRAMS:
                if name not in existing:
                    db.session.add(Program(name=name))
            db.session.flush()
        except Exception as e:
            print("⚠️ AVISO: No encontré models.Program. Crea el modelo para usar el seeder de programas.")
            Program = None

        # Coordinadores (usuarios staff: email + NIP; control_number puede ser None)
        try:
            from models.coordinator import Coordinator
            from models.program_coordinator import ProgramCoordinator
        except Exception:
            Coordinator = ProgramCoordinator = None
            print("⚠️ AVISO: No encontré models.Coordinator/ProgramCoordinator. Crea estos modelos para mapear carreras.")

        coord_users = []
        for full_name, email, nip, office_hours in COORDINATORS:
            u = db.session.query(User).filter_by(email=email).first()
            if not u:
                u = User(
                    role_id=roles["coordinator"].id,
                    control_number=None,
                    nip_hash=hash_nip(nip),
                    full_name=full_name,
                    email=email,
                    is_active=True,
                )
                db.session.add(u)
                db.session.flush()
            else:
                u.role_id = roles["coordinator"].id
                u.nip_hash = hash_nip(nip)
                u.is_active = True
            coord_users.append(u)

            # Fila en coordinators + mapeo a programas
            if Coordinator and Program and ProgramCoordinator:
                c = db.session.query(Coordinator).filter_by(user_id=u.id).first()
                if not c:
                    c = Coordinator(user_id=u.id, contact_email=email, office_hours=office_hours)
                    db.session.add(c)
                    db.session.flush()

                # asignar algunos programas (ejemplo: alternar)
                progs = db.session.query(Program).order_by(Program.id).all() if Program else []
                for idx, p in enumerate(progs):
                    if idx % len(COORDINATORS) == coord_users.index(u):
                        exists = db.session.query(ProgramCoordinator).filter_by(program_id=p.id, coordinator_id=c.id).first()
                        if not exists:
                            db.session.add(ProgramCoordinator(program_id=p.id, coordinator_id=c.id))

        # Usuario de servicio social
        ss_name, ss_email, ss_nip = SOCIAL_SERVICE
        ss = db.session.query(User).filter_by(email=ss_email).first()
        if not ss:
            ss = User(
                role_id=roles["social_service"].id,
                control_number=None,
                nip_hash=hash_nip(ss_nip),
                full_name=ss_name,
                email=ss_email,
                is_active=True,
            )
            db.session.add(ss)
        else:
            ss.role_id = roles["social_service"].id
            ss.nip_hash = hash_nip(ss_nip)
            ss.is_active = True

        # Disponibilidad + slots (si existen modelos)
        try:
            from models.availability_window import AvailabilityWindow
            from models.time_slot import TimeSlot

            # Para cada coordinador, crear 25–27 09:00–13:00
            for u in coord_users:
                # localizar fila en coordinators
                if Coordinator:
                    c = db.session.query(Coordinator).filter_by(user_id=u.id).first()
                    if not c:
                        continue
                    for d in DAYS:
                        start_dt = datetime.combine(d, START)
                        end_dt = datetime.combine(d, END)
                        aw = db.session.query(AvailabilityWindow).filter_by(
                            coordinator_id=c.id, start_time=start_dt, end_time=end_dt, slot_minutes=SLOT_MINUTES
                        ).first()
                        if not aw:
                            aw = AvailabilityWindow(
                                coordinator_id=c.id, start_time=start_dt, end_time=end_dt, slot_minutes=SLOT_MINUTES
                            )
                            db.session.add(aw)
                            db.session.flush()

                        # Generar slots de 10 min
                        for st in daterange(start_dt, end_dt, SLOT_MINUTES):
                            exists = db.session.query(TimeSlot).filter_by(
                                coordinator_id=c.id, start_time=st
                            ).first()
                            if not exists:
                                db.session.add(TimeSlot(
                                    coordinator_id=c.id,
                                    start_time=st,
                                    end_time=st + timedelta(minutes=SLOT_MINUTES),
                                    is_booked=False
                                ))
        except Exception as e:
            print("⚠️ AVISO: No encontré models.AvailabilityWindow/TimeSlot. Crea estos modelos para generar slots.")

        db.session.commit()
        print("✅ Seed coordinadores/programas listo.")
        for u in coord_users:
            print(f"   - {u.full_name} | {u.email} | NIP=1234")
        print(f"   - Servicio Social | {ss.email} | NIP=1234")
        if Program:
            print("   - Programas cargados.")

if __name__ == "__main__":
    main()
