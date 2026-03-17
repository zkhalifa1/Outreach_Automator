@echo off
echo ============================================
echo   Outreach Automation Tool - Setup
echo ============================================
echo.

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [OK] Python found.
echo.

:: Create virtual environment
echo Creating virtual environment...
if not exist "backend\venv" (
    python -m venv backend\venv
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

:: Activate and install dependencies
echo.
echo Installing Python dependencies...
call backend\venv\Scripts\activate.bat
pip install -r backend\requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo [OK] Dependencies installed.

:: Create .env from example if it doesn't exist
echo.
if not exist ".env" (
    copy .env.example .env >nul
    echo [SETUP] Created .env file from template.
    echo.
    echo ============================================
    echo   IMPORTANT: Configure your .env file
    echo ============================================
    echo.
    echo Please edit the .env file in this folder and set:
    echo   1. AZURE_CLIENT_ID    - from your Azure app registration
    echo   2. AZURE_TENANT_ID    - your Microsoft 365 tenant ID
    echo   3. ONEDRIVE_FILE_PATH - path to your Excel file in OneDrive
    echo.
    echo Then run start.bat to launch the tool.
    echo.
) else (
    echo [OK] .env file already exists.
)

:: Create data directory
if not exist "backend\data" mkdir backend\data

echo.
echo ============================================
echo   Setup complete!
echo ============================================
echo.
echo Next steps:
echo   1. Edit .env with your Azure credentials and OneDrive path
echo   2. Run start.bat to launch the tool
echo   3. Open http://localhost:8000 in your browser
echo.
pause
