FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GRANITE_MODEL_ID=ibm-granite/granite-guardian-3.2-3b-a800m \
    GREAT_WORK_GUARDIAN_MODE=local \
    GREAT_WORK_GUARDIAN_LOCAL_PATH=/app/models/guardian

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm -rf /var/lib/apt/lists/*

COPY app.py /app/app.py

EXPOSE 8085

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8085"]
