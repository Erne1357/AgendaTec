from models import db
from models.user import User
from models.role import Role
from utils.security import verify_nip

def authenticate(control_number: str, nip: str):
    """
    Retorna dict con {id, role, control_number, full_name} si ok, o None si falla.
    Solo autenticamos estudiantes por ahora (tienen control_number).
    """
    # Busca usuario activo por control_number
    user: User | None = (
        db.session.query(User)
        .filter(User.control_number == control_number, User.is_active == True)  # noqa: E712
        .first()
    )
    if not user or not user.nip_hash:
        return None

    # Verifica NIP
    if not verify_nip(nip, user.nip_hash):
        return None

    role_name = user.role.name if user.role else None

    return {
        "id": user.id,
        "role": role_name,
        "control_number": user.control_number,
        "full_name": user.full_name,
        "email": user.email,
    }
