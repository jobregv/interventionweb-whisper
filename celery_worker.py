from .tasks import celery

# Este archivo se usa para lanzar el worker desde la línea de comandos
# Ejecuta: celery -A celery_worker.celery worker --loglevel=info --concurrency=3
