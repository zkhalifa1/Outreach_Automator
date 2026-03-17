@echo off
echo ============================================
echo   Outreach Automation Tool - Starting...
echo ============================================
echo.

:: Check .env exists
if not exist ".env" (
    echo [ERROR] No .env file found. Run setup.bat first.
    pause
    exit /b 1
)

:: Check virtual environment exists
if not exist "backend\venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

:: Activate virtual environment
call backend\venv\Scripts\activate.bat

:: Start the server
echo Starting server at http://localhost:8000
echo Press Ctrl+C to stop.
echo.

cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000

:: If server exits
echo.
echo Server stopped.
pause
