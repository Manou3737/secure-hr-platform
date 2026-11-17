
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=America/New_York

WORKDIR /app

# Installer les mises à jour système et les données de fuseaux horaires
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Installer les dépendances Python depuis le lockfile vérifié
COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r /app/requirements.lock

# Copier le code Django et les schedulers
COPY backend/ /app/
COPY deploy/retention_scheduler.py /app/retention_scheduler.py
COPY deploy/notification_scheduler.py /app/notification_scheduler.py

# Créer les répertoires nécessaires
RUN mkdir -p /app/logs /app/staticfiles

# Exécuter l'application avec un utilisateur non privilégié
RUN addgroup --system django \
    && adduser --system --ingroup django django \
    && chown -R django:django /app

USER django

EXPOSE 8000
HEALTHCHECK --interval=30s \
    --timeout=5s \
    --start-period=30s \
    --retries=3 \
    CMD ["python", "-c", "import socket; s=socket.create_connection(('127.0.0.1', 8000), timeout=3); s.close()"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
