"""
CRM Service Entry Point

Run the CRM service using:
    python run.py

Or for development with auto-reload:
    uvicorn app.main:app --reload --port 8001
"""
import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
