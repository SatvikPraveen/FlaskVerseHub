"""Gunicorn configuration for FlaskVerseHub.

gevent + gevent-websocket workers keep Flask-SocketIO connections alive.
Scale horizontally with ``WEB_CONCURRENCY``; when running more than one
worker, set ``SOCKETIO_MESSAGE_QUEUE`` (Redis) so events reach every worker.
"""

import multiprocessing
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", min(2, multiprocessing.cpu_count())))
worker_class = "geventwebsocket.gunicorn.workers.GeventWebSocketWorker"
worker_connections = int(os.environ.get("WORKER_CONNECTIONS", "1000"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))
graceful_timeout = 30
keepalive = 5
max_requests = int(os.environ.get("MAX_REQUESTS", "2000"))
max_requests_jitter = 200
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(L)ss "%(a)s" req=%({x-request-id}o)s'
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "*")
preload_app = False  # gevent monkey-patching must happen per worker
