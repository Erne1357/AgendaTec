#!/usr/bin/env bash
set -euo pipefail

# Verificación mínima
if [ ! -f "/app/src/wsgi.py" ]; then
  echo "ERROR: /app/src/wsgi.py no existe. ¿Montaste ../backend en /app/src?"
  ls -la /app || true
  ls -la /app/src || true
  exit 1
fi

# Lanzar Gunicorn con Eventlet (soporte WebSockets)
# --chdir /app/src para que 'wsgi:app' resuelva bien
exec gunicorn \
  --config /etc/gunicorn/gunicorn.conf.py \
  --chdir /app/src \
  wsgi:app
