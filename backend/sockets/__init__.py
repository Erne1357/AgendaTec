# Sockets/__init__.py
from flask_socketio import SocketIO
from flask import current_app, request, g
from utils.redis_conn import REDIS_URL, REDIS_HOST, REDIS_PORT
from utils.jwt_tools import decode_jwt
from models import db
import os

# --- Config por defecto (puedes sobreescribir con env) ---
REDIS_QUEUE_URL = (
    os.getenv("SOCKET_IO_REDIS_URL")
    or REDIS_URL
    or f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
)

# Si puedes, limita a tu dominio, ej.: "https://midominio.com"
CORS_ORIGINS = os.getenv("SOCKET_IO_CORS", "*")

socketio = SocketIO(
    async_mode="eventlet",          # con gunicorn worker_class=eventlet
    message_queue=REDIS_QUEUE_URL,  # <- clave para >1 worker
    cors_allowed_origins=CORS_ORIGINS,
    cookie=None,                    # no crea cookie extra; usas la tuya (agendatec_token)
    ping_interval=25,               # latidos para detectar desconexión
    ping_timeout=60,                # si no responde en 60s, cierra
    max_http_buffer_size=2 * 1024 * 1024,  # ~2MB por evento (ajusta si subes blobs)
    logger=False,                   # pon True si quieres debug
    engineio_logger=False,
    always_connect=True             # deja que el connect corra y tú decidas si aceptas
)

# ------- Seguridad y limpieza -------

@socketio.on("connect")
def _on_connect(auth=None):
    """
    Autentica desde la cookie 'agendatec_token'.
    Si no es válido, rechaza la conexión (return False).
    """
    try:
        token = request.cookies.get("agendatec_token")
        data = decode_jwt(token) if token else None
        if not data:
            return False  # rechaza
        # Guarda el usuario en 'g' para handlers de eventos
        g.current_user = data
        return True
    except Exception:
        current_app.logger.exception("Error autenticando en connect()")
        return False

@socketio.on("disconnect")
def _on_disconnect():
    # Limpieza ligera (si la necesitas)
    try:
        db.session.remove()
    except Exception:
        pass

# Manejo global de excepciones en cualquier evento
@socketio.on_error_default
def _socketio_error_handler(e):
    try:
        db.session.rollback()
    except Exception:
        pass
    try:
        db.session.remove()
    except Exception:
        pass
    current_app.logger.exception("Excepción no controlada en Socket.IO")

# ------- Registro de eventos de tu app -------

from .slots import register_slot_events
from .requests import register_request_events
from .notifications import register_notification_events

def init_socketio(app):
    # Si quieres sobreescribir desde config/env al iniciar:
    socketio.init_app(app, message_queue=os.getenv("SOCKET_IO_REDIS_URL") or REDIS_QUEUE_URL)
    register_slot_events(socketio)
    register_request_events(socketio)
    register_notification_events(socketio)
    return socketio
