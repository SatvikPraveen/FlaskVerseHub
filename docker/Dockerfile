# syntax=docker/dockerfile:1.7
# Multi-stage build: wheels are compiled in a builder image and copied into a
# slim runtime that runs as an unprivileged user.

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements/ requirements/
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --upgrade pip wheel \
    && /opt/venv/bin/pip install -r requirements/prod.txt
COPY pyproject.toml README.md ./
COPY app/ app/
COPY experiments/ experiments/
RUN /opt/venv/bin/pip install . --no-deps

FROM python:${PYTHON_VERSION}-slim AS runtime
ARG BUILD_SHA=dev
LABEL org.opencontainers.image.title="FlaskVerseHub" \
      org.opencontainers.image.source="https://github.com/SatvikPraveen/FlaskVerseHub" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.revision="${BUILD_SHA}"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    FLASK_APP=wsgi:app FLASK_CONFIG=production BUILD_SHA=${BUILD_SHA} \
    PORT=8000 WEB_CONCURRENCY=2
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app wsgi.py manage.py ./
COPY --chown=app:app app/ app/
COPY --chown=app:app experiments/ experiments/
COPY --chown=app:app migrations/ migrations/
COPY --chown=app:app docker/gunicorn.conf.py docker/entrypoint.sh docker/
RUN chmod +x docker/entrypoint.sh && mkdir -p instance && chown -R app:app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/health" || exit 1
ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["gunicorn", "--config", "docker/gunicorn.conf.py", "wsgi:app"]
