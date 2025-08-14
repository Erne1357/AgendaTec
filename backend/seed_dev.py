import os
from app import create_app
from models import db
from models.user import User
from models.role import Role
from utils.security import hash_nip

def main():
    app = create_app()
    with app.app_context():
        student_role = db.session.query(Role).filter_by(name="student").first()
        if not student_role:
            # fallback si no cargaste DML de roles
            student_role = Role(name="student")
            db.session.add(student_role)
            db.session.commit()

        # upsert estudiante demo
        u = db.session.query(User).filter_by(control_number="12345678").first()
        if not u:
            u = User(
                role_id=student_role.id,
                control_number="12345678",
                nip_hash=hash_nip("1234"),
                full_name="Estudiante Demo",
                email="estudiante@example.com",
                is_active=True,
            )
            db.session.add(u)
        else:
            u.nip_hash = hash_nip("1234")
            u.is_active = True

        db.session.commit()
        print("✅ Seed listo: Usuario=12345678, NIP=1234")

if __name__ == "__main__":
    main()
