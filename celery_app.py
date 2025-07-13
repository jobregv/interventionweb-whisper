# 📁 transcription_service/celery_app.py
from celery import Celery
from config import Config
import logging

# Validar configuración al inicio
Config.validate()

logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Configuración de Celery con variables de entorno
celery_app = Celery(
    "transcription_worker",
    broker=Config.REDIS_URL,
    backend=Config.REDIS_URL,
    include=['tasks']
)

# Configuración optimizada y configurable
celery_app.conf.update(
    # Serialización
    task_serializer='pickle',
    accept_content=['pickle'],
    result_serializer='pickle',
    
    # Timezone
    timezone='UTC',
    enable_utc=True,
    
    # Performance
    result_expires=3600,
    worker_prefetch_multiplier=Config.WORKER_PREFETCH,
    task_acks_late=True,
    worker_max_tasks_per_child=50,
    
    # Timeouts
    task_time_limit=Config.TASK_TIME_LIMIT,
    task_soft_time_limit=Config.TASK_TIME_LIMIT - 30,
    
    # Logging
    worker_log_level=Config.LOG_LEVEL,
    task_track_started=True,
    
    # Routing
    task_routes={
        'transcribe_audio_with_callback': {'queue': 'transcription'},
    },
    
    # Error handling
    task_reject_on_worker_lost=True,
    task_acks_on_failure_or_timeout=True,
)

logger.info(f"✅ Celery configurado")
logger.info(f"   - Redis: {Config.REDIS_URL}")
logger.info(f"   - Concurrency: {Config.WORKER_CONCURRENCY}")
logger.info(f"   - Task Time Limit: {Config.TASK_TIME_LIMIT}s")