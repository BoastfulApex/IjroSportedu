import multiprocessing

# Bind
bind = "127.0.0.1:8000"

# Workers
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5

# Logging
accesslog = "/var/log/buyruqsportedu/gunicorn-access.log"
errorlog  = "/var/log/buyruqsportedu/gunicorn-error.log"
loglevel  = "info"

# Process
daemon = False
pidfile = "/var/run/buyruqsportedu/gunicorn.pid"
