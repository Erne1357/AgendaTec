# Sockets/__init__.py
from flask_socketio import SocketIO
from utils.redis_conn import REDIS_URL, REDIS_HOST, REDIS_PORT
import os

socketio = SocketIO(
    async_mode="eventlet",       # para dev; en prod combinarás con gunicorn/eventlet
    cors_allowed_origins="*",    # si ya usas cookies same-site Lax, puedes restringir a tu host
    message_queue=os.getenv("SOCKET_IO_REDIS_URL") or REDIS_URL or f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
    cookie=None                   # no seteamos cookie aparte; usamos la tuya (agendatec_token)
)

from .slots import register_slot_events
def init_socketio(app):
    socketio.init_app(app)
    register_slot_events(socketio)
    return socketio