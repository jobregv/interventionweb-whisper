# 📁 transcription_service/config.py - VPS VERSION OPTIMIZADO
import os
import subprocess
import socket
from typing import Optional

# Cargar archivo .env si existe
def load_env_file():
    """Carga variables del archivo .env si existe"""
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        print(f"📁 Cargando configuración desde: {env_file}")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        return True
    return False

# Cargar .env al importar
load_env_file()

class Config:
    """Configuración centralizada usando variables de entorno"""
    
    # Redis Configuration
    REDIS_URL: str = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Whisper Model Configuration
    WHISPER_MODEL: str = os.getenv('WHISPER_MODEL', 'medium')
    WHISPER_DEVICE: str = os.getenv('WHISPER_DEVICE', 'cpu')
    WHISPER_COMPUTE_TYPE: str = os.getenv('WHISPER_COMPUTE_TYPE', 'int8')
    
    # 🚀 Optimizaciones Whisper
    WHISPER_NUM_WORKERS: int = int(os.getenv('WHISPER_NUM_WORKERS', '1'))
    WHISPER_CPU_THREADS: int = int(os.getenv('WHISPER_CPU_THREADS', '1'))
    WHISPER_WORD_TIMESTAMPS: bool = os.getenv('WHISPER_WORD_TIMESTAMPS', 'true').lower() == 'true'
    
    # Celery Configuration
    WORKER_CONCURRENCY: int = int(os.getenv('WORKER_CONCURRENCY', '3'))
    WORKER_PREFETCH: int = int(os.getenv('WORKER_PREFETCH', '1'))
    TASK_TIME_LIMIT: int = int(os.getenv('TASK_TIME_LIMIT', '300'))  # 5 minutes
    
    # Callback Configuration
    CALLBACK_TIMEOUT: int = int(os.getenv('CALLBACK_TIMEOUT', '10'))
    CALLBACK_RETRIES: int = int(os.getenv('CALLBACK_RETRIES', '3'))
    
    # 🎯 VPS Configuration - Backend en Railway
    BACKEND_URL: str = os.getenv('BACKEND_URL', 'https://interventionweb-backend-development.up.railway.app')
    
    # File Configuration
    MAX_FILE_SIZE: int = int(os.getenv('MAX_FILE_SIZE', '50')) * 1024 * 1024  # 50MB default
    TEMP_DIR: str = os.getenv('TEMP_DIR', '/tmp')
    
    # Logging
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    # API Configuration
    API_HOST: str = os.getenv('API_HOST', '0.0.0.0')
    API_PORT: int = int(os.getenv('API_PORT', '8000'))
    
    @classmethod
    def get_callback_base_url(cls) -> str:
        """
        🌐 Construye la URL base para callbacks desde VPS a Railway
        """
        return cls.BACKEND_URL
    
    @classmethod
    def test_spring_boot_connectivity(cls) -> bool:
        """
        🧪 Testa conectividad con Spring Boot
        """
        try:
            import requests
            test_url = f"{cls.get_callback_base_url()}/health"
            response = requests.get(test_url, timeout=5)
            
            if response.status_code == 200:
                print(f"✅ Spring Boot accesible en: {test_url}")
                return True
            else:
                print(f"⚠️ Spring Boot responde pero con código: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ No se puede conectar a Spring Boot: {e}")
            print(f"   URL probada: {cls.get_callback_base_url()}")
            return False
    
    @classmethod
    def validate(cls):
        """Valida la configuración al inicio"""
        print(f"🔍 Validando configuración VPS...")
        print(f"   - Redis URL: {cls.REDIS_URL}")
        print(f"   - Whisper Model: {cls.WHISPER_MODEL}")
        print(f"   - Whisper Compute Type: {cls.WHISPER_COMPUTE_TYPE}")
        print(f"   - Whisper Workers: {cls.WHISPER_NUM_WORKERS}")
        print(f"   - Whisper CPU Threads: {cls.WHISPER_CPU_THREADS}")
        print(f"   - Word Timestamps: {cls.WHISPER_WORD_TIMESTAMPS}")
        print(f"   - Worker Concurrency: {cls.WORKER_CONCURRENCY}")
        print(f"   - Max File Size: {cls.MAX_FILE_SIZE // (1024*1024)}MB")
        print(f"   - Log Level: {cls.LOG_LEVEL}")
        
        # Mostrar configuración VPS->Railway
        print(f"\n🌐 Configuración VPS->Railway:")
        callback_url = cls.get_callback_base_url()
        print(f"   - Backend URL: {callback_url}")
        print(f"   - API Host: {cls.API_HOST}:{cls.API_PORT}")
        print(f"   - Configuración: VPS OPTIMIZADA")
        
        print(f"✅ Configuración validada")
        return True