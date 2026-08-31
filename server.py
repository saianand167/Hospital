"""
SIH26047 — MediKiosk FastAPI Backend Server Launcher
Run with:
    python server.py
"""

import sys
import os
from pathlib import Path

# Set up paths so part3/backend/app is imported as 'app', not hospital/app.py
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "part3" / "backend"

# Ensure backend directory is first in sys.path and root is removed
sys.path.insert(0, str(BACKEND_DIR))
sys.path = [p for p in sys.path if p not in (str(ROOT_DIR), "", ".")]

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        app_dir=str(BACKEND_DIR),
        host="0.0.0.0",
        port=8000,
        reload=False,
        timeout_keep_alive=120  # Allow long Groq AI calls (doctor summary, RAG) up to 120s
    )
