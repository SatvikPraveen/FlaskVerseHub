"""Structured logging, request correlation, timing, and Prometheus metrics.

Each request receives (or propagates) an ``X-Request-ID``. The identifier is
bound to the structlog context so every log line emitted while handling that
request carries it, and it is echoed on the response for client-side
correlation. Slow database queries are logged with their statement and
duration so performance regressions are visible without a profiler.
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from typing import Any

import structlog
from flask import Flask, Response, g, request
from flask_sqlalchemy.record_queries import get_recorded_queries

log = structlog.get_logger("flaskversehub")


def configure_logging(app: Flask) -> None:
    """Route stdlib logging through structlog with console or JSON rendering."""
    level = logging.getLevelName(str(app.config.get("LOG_LEVEL", "INFO")).upper())
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if app.config.get("LOG_JSON")
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=False,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    for noisy in ("werkzeug", "engineio", "socketio"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))
    app.logger.handlers = []
    app.logger.propagate = True


def register_request_hooks(app: Flask) -> None:
    """Bind request ids, measure latency and surface slow queries."""
    header = str(app.config.get("REQUEST_ID_HEADER", "X-Request-ID"))
    slow_threshold = float(app.config.get("SLOW_QUERY_THRESHOLD_SECONDS", 0.5))

    @app.before_request
    def _start_request() -> None:
        request_id = request.headers.get(header) or uuid.uuid4().hex
        g.request_id = request_id
        g.request_started = time.perf_counter()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id, method=request.method, path=request.path
        )

    @app.after_request
    def _finish_request(response: Response) -> Response:
        request_id = getattr(g, "request_id", None)
        if request_id:
            response.headers[header] = request_id
        started = getattr(g, "request_started", None)
        if started is not None:
            duration_ms = (time.perf_counter() - started) * 1000
            response.headers["Server-Timing"] = f"app;dur={duration_ms:.1f}"
            if app.config.get("SQLALCHEMY_RECORD_QUERIES"):
                for query in get_recorded_queries():
                    if query.duration >= slow_threshold:
                        log.warning(
                            "slow_query",
                            duration_ms=round(query.duration * 1000, 1),
                            statement=query.statement,
                            location=query.location,
                        )
            if not request.path.startswith("/static"):
                log.info(
                    "request",
                    status=response.status_code,
                    duration_ms=round(duration_ms, 1),
                    endpoint=request.endpoint,
                )
        return response

    @app.teardown_request
    def _clear_context(_exc: BaseException | None) -> None:
        structlog.contextvars.clear_contextvars()


def register_metrics(app: Flask) -> None:
    """Expose Prometheus metrics at ``/metrics`` when enabled."""
    if not app.config.get("METRICS_ENABLED", True):
        return
    from prometheus_flask_exporter import PrometheusMetrics

    metrics = PrometheusMetrics(
        app,
        group_by="endpoint",
        default_labels={"app": app.config.get("APP_NAME", "flaskversehub")},
        excluded_paths=["^/static/", "^/metrics$"],
    )
    metrics.info(
        "flaskversehub_build",
        "Build information",
        version=str(app.config.get("APP_VERSION")),
        sha=str(app.config.get("BUILD_SHA")),
    )
    app.extensions["prometheus_metrics"] = metrics


def init_app(app: Flask) -> None:
    configure_logging(app)
    register_request_hooks(app)
    register_metrics(app)
    if app.config.get("SENTRY_DSN"):  # pragma: no cover - requires the optional SDK
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=app.config["SENTRY_DSN"], traces_sample_rate=0.1)
        except ImportError:
            log.warning("sentry_sdk_missing", hint="pip install sentry-sdk[flask]")


__all__ = ["configure_logging", "init_app", "log", "register_metrics", "register_request_hooks"]
