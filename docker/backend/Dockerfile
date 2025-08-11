FROM python:3.12-slim

#zona horaria
RUN apt-get update && apt-get install -y tzdata && \
    ln -snf /usr/share/zoneinfo/America/Chihuahua /etc/localtime && \
    echo "America/Chihuahua" > /etc/timezone && \
    dpkg-reconfigure -f noninteractive tzdata

# Dependencias mínimas del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Evita .pyc y asegura logs en stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Carpeta de trabajo de la app
WORKDIR /app

# Requerimientos
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt


COPY docker/backend/entrypoint.sh /usr/local/bin/agenda-entrypoint
RUN chmod +x /usr/local/bin/agenda-entrypoint

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/agenda-entrypoint"]
