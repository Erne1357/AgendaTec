# sockets/requests.py
from flask import g, request
from flask_socketio import emit, join_room, leave_room
from utils.socket_auth import current_user_from_environ

NAMESPACE = "/requests"

def _room_ap_day(coord_id: int, day: str) -> str:
    return f"coord:ap:{coord_id}:{day}"

def _room_drops(coord_id: int) -> str:
    return f"coord:drops:{coord_id}"

def register_request_events(socketio):
    @socketio.on("connect", namespace=NAMESPACE)
    def on_connect():
        user = current_user_from_environ(request.environ)
        if not user:
            return False
        g.current_user = user
        emit("hello", {"msg": "WS /requests conectado"})

    @socketio.on("disconnect", namespace=NAMESPACE)
    def on_disconnect():
        pass

    # -------- Appointments (por día) ----------
    @socketio.on("join_ap_day", namespace=NAMESPACE)
    def on_join_ap_day(data):
        # esperado: {"coord_id": <int>, "day":"YYYY-MM-DD"}
        try:
            coord_id = int((data or {}).get("coord_id") or 0)
            day = (data or {}).get("day") or ""
        except Exception:
            emit("error", {"error": "bad_payload"})
            return
        if coord_id <= 0 or not day:
            emit("error", {"error": "invalid_join_ap_day"})
            return
        join_room(_room_ap_day(coord_id, day))
        emit("joined_ap_day", {"coord_id": coord_id, "day": day})

    @socketio.on("leave_ap_day", namespace=NAMESPACE)
    def on_leave_ap_day(data):
        try:
            coord_id = int((data or {}).get("coord_id") or 0)
            day = (data or {}).get("day") or ""
        except Exception:
            emit("error", {"error": "bad_payload"})
            return
        if coord_id <= 0 or not day:
            emit("error", {"error": "invalid_leave_ap_day"})
            return
        leave_room(_room_ap_day(coord_id, day))
        emit("left_ap_day", {"coord_id": coord_id, "day": day})

    # -------- Drops (1 room por coordinador) ----------
    @socketio.on("join_drops", namespace=NAMESPACE)
    def on_join_drops(data):
        try:
            coord_id = int((data or {}).get("coord_id") or 0)
        except Exception:
            emit("error", {"error": "bad_payload"})
            return
        if coord_id <= 0:
            emit("error", {"error": "invalid_join_drops"})
            return
        join_room(_room_drops(coord_id))
        emit("joined_drops", {"coord_id": coord_id})

# --------- Helpers para emitir desde rutas ----------
def broadcast_appointment_created(socketio, coord_id: int, day: str, payload: dict):
    socketio.emit("appointment_created", payload, to=_room_ap_day(coord_id, day), namespace=NAMESPACE)

def broadcast_drop_created(socketio, coord_id: int, payload: dict):
    socketio.emit("drop_created", payload, to=_room_drops(coord_id), namespace=NAMESPACE)

def broadcast_request_status_changed(socketio, coord_id: int, payload: dict):
    """
    payload sugerido:
    {
      "type": "APPOINTMENT" | "DROP",
      "request_id": int,
      "new_status": str,
      "day": "YYYY-MM-DD" | None
    }
    """
    # Emitimos a ambas salas potenciales (citas del día y drops). El cliente decide si refresca.
    day = payload.get("day")
    if day:
        socketio.emit("request_status_changed", payload,
                      to=_room_ap_day(coord_id, day), namespace=NAMESPACE)
    socketio.emit("request_status_changed", payload,
                  to=_room_drops(coord_id), namespace=NAMESPACE)
