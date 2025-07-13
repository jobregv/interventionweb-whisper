# 📁 transcription_service/tasks.py - VPS VERSION
import tempfile
import os
import logging
import requests
import time
from faster_whisper import WhisperModel
from urllib.parse import urlparse, urlunparse

from celery_app import celery_app
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Modelo por proceso para VPS
_process_model = None
_process_id = None

def get_whisper_model():
    """Obtiene modelo Whisper específico por proceso"""
    global _process_model, _process_id
    current_pid = os.getpid()
    
    if _process_model is None or _process_id != current_pid:
        logger.info(f"🔄 [PROCESS {current_pid}] Cargando modelo Whisper {Config.WHISPER_MODEL}...")
        start_time = time.time()
        
        _process_model = WhisperModel(
            Config.WHISPER_MODEL, 
            device=Config.WHISPER_DEVICE, 
            compute_type=Config.WHISPER_COMPUTE_TYPE
        )
        _process_id = current_pid
        
        load_time = time.time() - start_time
        logger.info(f"✅ [PROCESS {current_pid}] Modelo {Config.WHISPER_MODEL} cargado en {load_time:.2f}s")
    
    return _process_model

def fix_callback_url(original_url: str) -> str:
    """
    🎯 VPS: No necesita arreglos, devuelve URL tal como viene
    """
    return original_url

@celery_app.task(name="transcribe_audio_with_callback", bind=True)
def transcribe_audio_with_callback(self, audio_bytes: bytes, job_id: str = None, 
                                  callback_url: str = None, callback_token: str = None):
    temp_path = None
    actual_job_id = job_id or self.request.id
    process_id = os.getpid()
    
    fixed_callback_url = fix_callback_url(callback_url)
    
    try:
        logger.info(f"🎤 [PROCESS {process_id}] INICIANDO transcripción - JobID: {actual_job_id}")
        start_time = time.time()
        
        # 🔧 DETECTAR FORMATO DE AUDIO AUTOMÁTICAMENTE
        def detect_audio_format(audio_data):
            """Detecta el formato del archivo de audio por sus primeros bytes"""
            if audio_data.startswith(b'RIFF'):
                return ".wav"
            elif audio_data.startswith(b'\x1a\x45\xdf\xa3'):  # WebM/Matroska header
                return ".webm"
            elif audio_data.startswith(b'OggS'):
                return ".ogg"
            elif audio_data.startswith(b'ID3') or audio_data.startswith(b'\xff\xfb'):
                return ".mp3"
            elif audio_data.startswith(b'fLaC'):
                return ".flac"
            else:
                # Fallback: WebM es el más común desde navegadores
                logger.warning(f"⚠️ [PROCESS {process_id}] Formato no detectado, usando WebM por defecto")
                return ".webm"
        
        # Detectar formato correcto
        audio_format = detect_audio_format(audio_bytes)
        logger.info(f"🎵 [PROCESS {process_id}] Formato detectado: {audio_format}")
        
        # Crear archivo temporal con extensión correcta
        with tempfile.NamedTemporaryFile(suffix=audio_format, delete=False) as tmp:
            tmp.write(audio_bytes)
            temp_path = tmp.name
        
        # Validar tamaño de archivo
        file_size_mb = len(audio_bytes) / (1024 * 1024)
        logger.info(f"📁 [PROCESS {process_id}] Archivo: {file_size_mb:.1f}MB, Formato: {audio_format}")
        
        if len(audio_bytes) < 100:  # Menos de 100 bytes es definitivamente inválido
            raise ValueError(f"Archivo de audio demasiado pequeño: {len(audio_bytes)} bytes")
        
        # Obtener modelo y transcribir
        whisper_model = get_whisper_model()
        
        transcription_start = time.time()
        logger.info(f"🔄 [PROCESS {process_id}] TRANSCRIBIENDO con {Config.WHISPER_MODEL}...")
        
        try:
            segments, info = whisper_model.transcribe(
                temp_path, 
                beam_size=5, 
                language="es"
            )
        except Exception as transcription_error:
            # Error específico de transcripción
            if "Invalid data found" in str(transcription_error):
                raise ValueError(f"Archivo de audio corrupto o formato no válido: {transcription_error}")
            else:
                raise  # Re-lanzar otros errores
        
        segment_texts = [segment.text for segment in segments]
        transcription = "".join(segment_texts).strip()
        
        transcription_time = time.time() - transcription_start
        total_time = time.time() - start_time
        
        if not transcription:
            raise ValueError("Transcripción vacía")
        
        logger.info(f"✅ [PROCESS {process_id}] COMPLETADO - JobID: {actual_job_id}")
        logger.info(f"   📝 Texto: {transcription[:50]}...")
        logger.info(f"   ⏱️  Transcripción: {transcription_time:.2f}s")
        logger.info(f"   ⏱️  Total: {total_time:.2f}s")
        
        # 🏢 ENTERPRISE CALLBACK: Simple y directo
        if fixed_callback_url:
            callback_start = time.time()
            send_enterprise_callback(fixed_callback_url, actual_job_id, "completed", 
                                   transcription, None, callback_token, process_id)
            callback_time = time.time() - callback_start
            logger.info(f"📞 [PROCESS {process_id}] Callback enviado en {callback_time:.2f}s")
        
        return transcription
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        total_time = time.time() - start_time
        
        logger.error(f"❌ [PROCESS {process_id}] ERROR - JobID: {actual_job_id}")
        logger.error(f"   🐛 Error: {error_msg}")
        logger.error(f"   ⏱️  Tiempo: {total_time:.2f}s")
        
        # Callback de error
        if fixed_callback_url:
            send_enterprise_callback(fixed_callback_url, actual_job_id, "failed", 
                                   None, error_msg, callback_token, process_id)
        
        raise
        
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                logger.debug(f"🗑️ [PROCESS {process_id}] Archivo temporal eliminado")
            except Exception as e:
                logger.warning(f"⚠️ [PROCESS {process_id}] No se pudo eliminar {temp_path}: {e}")

def send_enterprise_callback(callback_url: str, job_id: str, status: str, 
                           transcription: str = None, error: str = None, 
                           callback_token: str = None, process_id: int = None):
    """
    🏢 ENTERPRISE CALLBACK: VPS -> Railway Backend
    
    Directo y confiable - Railway backend está siempre disponible.
    """
    if process_id is None:
        process_id = os.getpid()
    
    max_retries = 2  # Solo 2 intentos
    timeout = 10
    
    for attempt in range(1, max_retries + 1):
        try:
            payload = {
                "jobId": job_id,
                "status": status
            }
            
            if status == "completed" and transcription:
                payload["transcription"] = transcription
            elif status == "failed" and error:
                payload["error"] = error
            
            headers = {"Content-Type": "application/json"}
            if callback_token:
                headers["Authorization"] = f"Bearer {callback_token}"
            
            logger.info(f"📞 [PROCESS {process_id}] Callback VPS->Railway (intento {attempt}/{max_retries}) - JobID: {job_id}")
            
            response = requests.post(
                callback_url,
                json=payload,
                timeout=timeout,
                headers=headers
            )
            
            if response.status_code == 200:
                logger.info(f"✅ [PROCESS {process_id}] Callback exitoso - JobID: {job_id}")
                return
            else:
                logger.warning(f"⚠️ [PROCESS {process_id}] Callback falló: HTTP {response.status_code}")
                logger.debug(f"Response: {response.text}")
                
        except Exception as e:
            logger.error(f"❌ [PROCESS {process_id}] Error callback (intento {attempt}): {e}")
        
        # Solo 1 reintento con pausa mínima
        if attempt < max_retries:
            logger.info(f"⏳ [PROCESS {process_id}] Reintentando en 2s...")
            time.sleep(2)
    
    # Si falla, log pero no crash
    logger.error(f"💥 [PROCESS {process_id}] Callback falló definitivamente - JobID: {job_id}")
    logger.error(f"💡 [PROCESS {process_id}] Revisar conectividad VPS->Railway o logs del backend.")