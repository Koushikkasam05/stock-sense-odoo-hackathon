import os
import multiprocessing

# Gunicorn configuration file for StockSense production deployment
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = int(os.environ.get('WEB_CONCURRENCY', multiprocessing.cpu_count() * 2 + 1 if multiprocessing.cpu_count() else 4))
threads = int(os.environ.get('PYTHON_MAX_THREADS', 2))
worker_class = 'sync'
worker_connections = 1000
timeout = 120
keepalive = 5

# Logging
accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('LOG_LEVEL', 'info')

# Process naming
proc_name = 'stocksense_gunicorn'
