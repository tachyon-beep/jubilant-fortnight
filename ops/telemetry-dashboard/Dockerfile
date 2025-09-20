FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TELEMETRY_DB_PATH=/data/telemetry.db

WORKDIR /app

COPY pyproject.toml poetry.lock* requirements.txt* /tmp/deps/ 2>/dev/null || true
COPY ops/telemetry-dashboard/requirements.txt /tmp/dashboard-requirements.txt
RUN pip install --no-cache-dir -r /tmp/dashboard-requirements.txt

COPY great_work /app/great_work
COPY ops/telemetry-dashboard/app.py /app/app.py
COPY ops/telemetry-dashboard/templates /app/templates

EXPOSE 8081

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]
