# Chạy từ bất kỳ đâu: .\scripts\run_dev.ps1
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# 1. Bật Postgres + Redis (nếu đang chạy rồi thì giữ nguyên), đợi healthy
docker compose up -d --wait
if ($LASTEXITCODE -ne 0) {
    Write-Host "Postgres/Redis chưa sẵn sàng. Mở Docker Desktop rồi chạy lại." -ForegroundColor Red
    exit 1
}

# 2. Mở cửa sổ mới chạy Django (dùng python trong venv, không cần activate)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Root\backend'; & '$Root\backend\.venv\Scripts\python.exe' manage.py runserver"

# 3. Mở cửa sổ mới chạy Vite
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Root\frontend'; npm run dev"

Write-Host "Backend:  http://127.0.0.1:8000/api/health/"
Write-Host "Swagger:  http://localhost:8000/api/docs/"
Write-Host "Mailpit:  http://localhost:8025"
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
