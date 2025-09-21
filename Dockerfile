# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for scientific stack (sentence-transformers/torch)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       git \
       libgomp1 \
       libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md LICENSE ./
COPY great_work ./great_work

# Install project
RUN pip install --upgrade pip \
    && pip install .

# Default runtime env can be provided via env-file or -e flags
# Expose no ports by default; the bot connects outbound to Discord

CMD ["python", "-m", "great_work.discord_bot"]

