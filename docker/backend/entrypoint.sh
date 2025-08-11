#!/usr/bin/env bash
set -euo pipefail

# Soluciona casos de CRLF en Windows
if command -v dos2unix >/dev/null 2>&1; then
  find /app/src -type f -name "*.sh" -exec dos2unix {} \; || true
fi

# Asegura que el código exista
if [ ! -f "/app/src/wsgi.py" ]; then
  echo "ERROR: /app/src/wsgi.py no existe. ¿Montaste ../backend en /app/src?"
  ls -la /app || true
  ls -la /app/src || true
  exit 1
fi

cd /app/src
# Arranca el servidor de desarrollo de Flask ejecutando wsgi.py directamente
exec python wsgi.py
