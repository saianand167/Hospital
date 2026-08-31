#!/usr/bin/env bash
# ============================================================
# SIH26047 — MediKiosk Unified Launcher (Linux / macOS)
# ============================================================

set -e

echo "============================================================"
echo "  SIH26047 — MediKiosk Case-Taking & Intake System          "
echo "============================================================"

# 1. Start Docker PostgreSQL
echo -e "\n[1/4] Checking Docker PostgreSQL Service..."
if command -v docker &> /dev/null; then
    echo "Starting Docker containers..."
    docker compose up -d
    sleep 3
else
    echo "[NOTICE] Docker command not found on PATH."
fi

# 2. Check Database Connectivity
echo -e "\n[2/4] Verifying PostgreSQL Database Connectivity..."
python -c "
import sys
sys.path.insert(0, '.')
try:
    from database.connection import check_db_health
    if check_db_health():
        print('✅ PostgreSQL Database connected successfully!')
    else:
        print('⚠️ PostgreSQL database is not reachable. Run: docker compose up -d')
except Exception as e:
    print(f'Database check: {e}')
"

# 3. Start Backend in Background
echo -e "\n[3/4] Launching MediKiosk Backend (FastAPI, Port 8000)..."
export PYTHONPATH="part3/backend:."
python -m uvicorn app.main:app --app-dir part3/backend --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

trap "kill $BACKEND_PID 2>/dev/null || true" EXIT

sleep 2

# 4. Start Unified Streamlit Frontend
echo -e "\n[4/4] Launching MediKiosk Unified UI (Streamlit, Port 8501)..."
echo "============================================================"
echo "  Opening MediKiosk in your browser: http://localhost:8501  "
echo "============================================================"

streamlit run app.py
