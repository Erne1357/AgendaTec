import os, time, jwt

SECRET = os.getenv("SECRET_KEY", "dev")

def encode_jwt(payload: dict, hours: int = 12) -> str:
    now = int(time.time())
    body = {**payload, "iat": now, "exp": now + hours*3600}
    return jwt.encode(body, SECRET, algorithm="HS256")

def decode_jwt(token: str|None):
    if not token:
        return None
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
