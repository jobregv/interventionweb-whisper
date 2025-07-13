# 📁 transcription_service/main.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from celery.result import AsyncResult
import logging
from typing import Optional
import time

from config import Config
from celery_app import celery_app
from tasks import transcribe_audio_with_callback

# Validar configuración
Config.validate()

logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Audio Transcription API",
    description="Enterprise Audio Transcription Service",
    version="2.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    job_id: Optional[str] = Form(None),
    callback_url: Optional[str] = Form(None),
    callback_token: Optional[str] = Form(None)
):
    try:
        start_time = time.time()
        logger.info(f"📤 Received file: {audio.filename} (job_id: {job_id})")
        
        # Validate audio content type
        if not audio.content_type or not audio.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only audio files are allowed."
            )
        
        # Read file with size validation
        audio_bytes = await audio.read()
        file_size_mb = len(audio_bytes) / (1024 * 1024)
        
        if len(audio_bytes) > Config.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {file_size_mb:.1f}MB. Maximum: {Config.MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        logger.info(f"📁 File read: {file_size_mb:.1f}MB")
        
        # Submit to Celery
        job = transcribe_audio_with_callback.apply_async(
            args=[audio_bytes],
            kwargs={
                'job_id': job_id,
                'callback_url': callback_url,
                'callback_token': callback_token
            },
            queue='transcription'
        )
        
        actual_job_id = job_id if job_id else job.id
        processing_time = time.time() - start_time
        
        logger.info(f"✅ Task submitted: {actual_job_id} (processing: {processing_time:.2f}s)")
        
        return {
            "job_id": actual_job_id,
            "status": "processing",
            "message": "Audio submitted for transcription",
            "file_size_mb": round(file_size_mb, 2),
            "estimated_duration": "2-5 minutes"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in /transcribe: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.get("/result/{job_id}")
def get_result(job_id: str):
    """Get transcription result by job ID"""
    try:
        logger.info(f"🔍 Querying result for job_id: {job_id}")
        result = AsyncResult(job_id, app=celery_app)
        
        response = {
            "job_id": job_id,
            "status": result.status.lower()
        }
        
        if result.failed():
            error_msg = str(result.result) if result.result else "Unknown error"
            logger.error(f"❌ Task {job_id} failed: {error_msg}")
            response.update({
                "status": "failed",
                "error": error_msg
            })
        elif result.ready():
            transcription = result.result
            logger.info(f"✅ Task {job_id} completed")
            response.update({
                "status": "completed",
                "transcription": transcription,
                "length": len(transcription) if transcription else 0
            })
        
        return response
            
    except Exception as e:
        logger.error(f"❌ Error querying result {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/health")
def health_check():
    """Enhanced health check"""
    try:
        # Check Celery connection
        i = celery_app.control.inspect()
        stats = i.stats()
        active_workers = len(stats) if stats else 0
        
        # Check Redis connection
        redis_info = celery_app.backend.client.info()
        
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "version": "2.0.0",
            "workers": {
                "active": active_workers,
                "configured_concurrency": Config.WORKER_CONCURRENCY
            },
            "redis": {
                "connected": True,
                "version": redis_info.get('redis_version', 'unknown')
            },
            "config": {
                "model": Config.WHISPER_MODEL,
                "device": Config.WHISPER_DEVICE,
                "max_file_size_mb": Config.MAX_FILE_SIZE // (1024*1024)
            }
        }
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.API_HOST, port=Config.API_PORT)