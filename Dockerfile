# Multi-Arch-Basisimage (amd64/arm64) — Architektur bewusst nicht festgelegt,
# lokal wird auf Apple Silicon entwickelt, der Zielserver ist x86_64.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    TZ=Europe/Berlin \
    DATA_DIR=/storage/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY export.py scheduler.py app.py wsgi.py entrypoint.sh DATENSATZBESCHREIBUNG.md ./
COPY templates/ templates/
COPY static/ static/

RUN chmod +x entrypoint.sh && mkdir -p /storage

EXPOSE 80

CMD ["./entrypoint.sh"]
