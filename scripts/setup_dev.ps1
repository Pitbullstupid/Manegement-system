# Chạy từ bất kỳ đâu: .\scripts\setup_dev.ps1
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Assert-Ok($msg) {
    if ($LASTEXITCODE -ne 0) { Write-Host "LỖI: $msg" -ForegroundColor Red; exit 1 }
}

# 1. Docker Desktop phải đang chạy
docker info 2>$null | Out-Null
Assert-Ok "Docker chưa chạy. Mở Docker Desktop, đợi 'Engine running' rồi chạy lại."

# 2. Tạo virtualenv bằng Python 3.12 (nếu chưa có) và cài thư viện
if (-not (Test-Path "backend\.venv")) {
    py -3.12 -m venv backend\.venv
    Assert-Ok "Không tạo được venv. Cần cài Python 3.12."
}
$Py = "$Root\backend\.venv\Scripts\python.exe"
& $Py -m pip install --upgrade pip
& $Py -m pip install -r backend\requirements\dev.txt
Assert-Ok "pip install thất bại"

# 3. Tạo .env từ .env.example, sinh SECRET_KEY ngẫu nhiên, ghi KHÔNG BOM
if (-not (Test-Path ".env")) {
    $key = & $Py -c "import secrets; print(secrets.token_urlsafe(50))"
    $text = [System.IO.File]::ReadAllText("$Root\.env.example")
    $text = $text -replace '(?m)^SECRET_KEY=[^\r\n]*', "SECRET_KEY=$key"
    $text = $text -replace '(?m)^DB_HOST=[^\r\n]*', 'DB_HOST=127.0.0.1'
    $text = $text -replace '(?m)^DB_PORT=[^\r\n]*', 'DB_PORT=5433'
    [System.IO.File]::WriteAllText("$Root\.env", $text, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Đã tạo .env"
}

# 4. Cài thư viện frontend
if (Test-Path "frontend\package.json") {
    Push-Location frontend
    npm install
    Pop-Location
    Assert-Ok "npm install thất bại"
}

# 5. Bật Postgres + Redis, --wait = đợi healthcheck báo healthy
docker compose up -d --wait
Assert-Ok "Postgres/Redis chưa healthy. Xem log: docker compose logs"

# 6. Tạo bảng hệ thống của Django
& $Py backend\manage.py migrate
Assert-Ok "migrate thất bại"

Write-Host "Setup xong. Chạy: .\scripts\run_dev.ps1" -ForegroundColor Green
