# PowerShell runner for MediKiosk Part 1

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " Starting MediKiosk Part 1 Services...   " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Start FastAPI Backend on Port 8001
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python -m uvicorn app.main:app --port 8001 --reload"

# Start Streamlit UI on Port 8501
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python -m streamlit run app/ui/streamlit_app.py --server.port 8501"

Write-Host "FastAPI Backend: http://127.0.0.1:8001/docs" -ForegroundColor Green
Write-Host "Streamlit UI:    http://127.0.0.1:8501" -ForegroundColor Green
