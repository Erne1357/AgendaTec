# Sockets/slots.py
from flask import request
from flask_socketio import Namespace, emit, join_room, leave_room, disconnect
from utils.socket_auth import current_user_from_environ

ALLOWED_DAYS_STR = {"2025-08-25", "2025-08-26", "2025-08-27"}  # mismo set que tu API

def room_for_day(day: str) -> str:
    return f"day:{day}"

class SlotsNamespace(Namespace):
    """
    Paso 1: Bootstrap
    - Autenticación por cookie JWT
    - join_day / leave_day
    - ping de prueba: hello
    (En el Paso 2 añadimos Redis y ‘snapshot’, hold/reserve reales)
    """

    def on_connect(self):
        user = current_user_from_environ(request.environ)
        if not user:
            # No autenticado → cortamos
            return False  # indica rechazo de conexión
        # Guardamos usuario en el scope del socket
        request.environ["__current_user__"] = user
        emit("hello", {"msg": f"Conectado como {user.get('name') or user.get('cn')}"})

    def on_disconnect(self):
        # Limpieza simple si quisieras
        pass

    def on_join_day(self, data):
        """
        data = {"day": "YYYY-MM-DD"}
        """
        user = request.environ.get("__current_user__")
        if not user:
            disconnect()
            return
        day = (data or {}).get("day", "")
        if day not in ALLOWED_DAYS_STR:
            emit("error", {"error": "day_not_allowed"})
            return

        join_room(room_for_day(day))
        emit("joined_day", {"day": day})

        # Paso 1: stub de snapshot (solo confirma). En Paso 2 devolveremos estados reales.
        emit("slots_snapshot", {
            "day": day,
            "items": []  # luego: slots disponibles + holds/booked
        })

    def on_leave_day(self, data):
        user = request.environ.get("__current_user__")
        if not user:
            disconnect()
            return
        day = (data or {}).get("day", "")
        if day in ALLOWED_DAYS_STR:
            leave_room(room_for_day(day))
            emit("left_day", {"day": day})
        else:
            emit("error", {"error": "day_not_allowed"})
