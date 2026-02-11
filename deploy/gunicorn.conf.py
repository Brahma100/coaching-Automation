import multiprocessing

bind = "127.0.0.1:8000"
workers = (multiprocessing.cpu_count() * 2) + 1
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 60
graceful_timeout = 30
keepalive = 5
loglevel = "info"
accesslog = "-"
errorlog = "-"
