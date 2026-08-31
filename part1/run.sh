#!/usr/bin/env bash
# Bash runner for MediKiosk Part 1

echo "Starting MediKiosk FastAPI Backend on port 8001..."
uvicorn app.main:app --port 8001 --reload &
BACKEND_PID=$!

echo "Starting Streamlit UI on port 8501..."
streamlit run app/ui/streamlit_app.py --server.port 8501 &
FRONTEND_PID=$!

echo "FastAPI Backend: http://127.0.0.1:8001/docs"
echo "Streamlit UI:    http://127.0.0.1:8501"

wait $BACKEND_PID $FRONTEND_PID
