from app import create_app
from sockets import socketio
app = create_app()

# Para desarrollo local 
if __name__ == "__main__":
    socketio.run(host="0.0.0.0", port=8080, debug=True)
