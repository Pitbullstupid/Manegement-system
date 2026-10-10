# Enterprise Project & Workflow Management System

Hệ thống quản lý dự án, công việc và quy trình phê duyệt nội bộ doanh nghiệp (kiểu Jira + Trello đơn giản hóa).

**Tech stack:** Django, Django REST Framework, PostgreSQL 16, Redis 7, React (Vite), Ant Design, Docker Compose.

## Yêu cầu

- Windows 11, PowerShell
- Docker Desktop
- Python 3.12
- Node.js LTS (20.19+ hoặc 22.12+)

## Chạy nhanh (Windows)

```powershell
.\scripts\setup_dev.ps1   # chạy 1 lần: venv, thư viện, .env, Docker, migrate
.\scripts\run_dev.ps1     # mỗi lần dev: bật Docker, Django, Vite
```

Mở http://localhost:5173 để xem trạng thái hệ thống.

## Cấu trúc

- `backend/`: Django REST API
- `frontend/`: React (Vite)
- `scripts/`: script setup và chạy dev
- `docker-compose.yml`: PostgreSQL + Redis

## Ghi chú

- Postgres trong Docker dùng cổng 5433 để tránh đụng Postgres cài sẵn trên máy.
- Health check: `GET /api/health/`
