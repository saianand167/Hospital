# ============================================================
# SIH26047 - MediKiosk Unified Launcher (Windows PowerShell)
# ============================================================

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  SIH26047 - MediKiosk Case-Taking and Intake System        " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Start Backend Server (FastAPI on Port 8000 via server.py)
Write-Host "`n[1/2] Launching MediKiosk Backend (FastAPI on Port 8000)..." -ForegroundColor Yellow
$backendProcess = Start-Process -FilePath "python" -ArgumentList "server.py" -PassThru -NoNewWindow

Start-Sleep -Seconds 3

# 2. Start Unified Streamlit UI (Port 8501)
Write-Host "`n[2/2] Launching MediKiosk Unified UI (Streamlit on Port 8501)..." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Opening MediKiosk in your browser: http://localhost:8501  " -ForegroundColor Cyan
Write-Host "  Press Ctrl+C in this terminal to exit                     " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

try {
    streamlit run app.py
}
finally {
    if ($backendProcess -and !$backendProcess.HasExited) {
        Write-Host "`nStopping backend process..." -ForegroundColor Yellow
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
