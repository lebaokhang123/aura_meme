@echo off
setlocal
title AuraMeme - Run locally
pushd "%~dp0"
if errorlevel 1 goto error

where node >nul 2>&1
if errorlevel 1 goto missing_node
where npm >nul 2>&1
if errorlevel 1 goto missing_node

if not exist "package.json" (
    echo ERROR: Place run.bat in the AuraMeme project folder.
    goto error
)

if not exist "node_modules\.bin\vite.cmd" (
    echo Installing dependencies. Internet is required on the first run...
    call npm install
    if errorlevel 1 goto error
)

echo Starting AuraMeme. The browser will open automatically.
echo If port 5173 is busy, Vite will use the next available port.
echo Keep this window open. Press Ctrl+C to stop the website.
call npm run dev -- --open
if errorlevel 1 goto error
popd
exit /b 0

:missing_node
echo ERROR: Node.js and npm are required.
echo Install Node.js 22.12 or newer from https://nodejs.org
echo Then close this window and double-click run.bat again.

:error
echo.
echo AuraMeme could not start. Please check the message above.
echo Check the error above, then try again.
pause
popd
exit /b 1
