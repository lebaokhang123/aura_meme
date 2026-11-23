@echo off
setlocal
echo ====================================================================
echo AURAMEME TASK 9 - OWNER QA LAUNCHER
echo Workspace: %~dp0
echo ====================================================================

set "ENV_REL=..\.env.qa"
if not exist "%~dp0.env.qa" (
    if exist "%~dp0backend\demo.local\.env" (
        set "ENV_REL=demo.local\.env"
    ) else (
        echo [LOI] Khong tim thay file cau hinh cuc bo .env.qa hoac backend\demo.local\.env
        echo Vui long kiem tra file cau hinh truoc khi khoi dong.
        pause
        exit /b 1
    )
)

echo 1. Kiem tra backend virtual environment...
if not exist "%~dp0backend\.venv\Scripts\python.exe" (
    echo [LOI] Thieu backend\.venv\Scripts\python.exe
    pause
    exit /b 1
)

echo 2. Khoi dong Backend FastAPI tai http://127.0.0.1:8000 ...
start "AuraMeme Backend (QA)" /min /D "%~dp0backend" cmd /c ".\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file %ENV_REL%"

echo 3. Cho Backend san sang...
timeout /t 3 /nobreak > nul

echo 4. Khoi dong Frontend Vite tai http://localhost:5173 ...
start "AuraMeme Frontend (QA)" /D "%~dp0frontend" cmd /c "npm.cmd run dev -- --host localhost --port 5173"

echo 5. Mo trinh duyet...
timeout /t 2 /nobreak > nul
start http://localhost:5173

echo ====================================================================
echo AuraMeme QA da san sang tai http://localhost:5173!
echo Dong cac cua so cmd de dung server.
echo ====================================================================
