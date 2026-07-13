@echo off
setlocal enabledelayedexpansion

REM --- CHECK AND BOOTSTRAP PYTHON FIRST (SILENTLY) ---
python --version >nul 2>&1
if %errorlevel% equ 0 (
    goto run_py
)

REM Search in common local and system paths if not in PATH
set "PYTHON_FOUND="
for /d %%d in ("%USERPROFILE%\AppData\Local\Programs\Python\Python*") do (
    if exist "%%d\python.exe" (
        set "PYTHON_PATH=%%d"
        set "PYTHON_FOUND=1"
    )
)
for /d %%d in ("%ProgramFiles%\Python*") do (
    if exist "%%d\python.exe" (
        set "PYTHON_PATH=%%d"
        set "PYTHON_FOUND=1"
    )
)
for /d %%d in ("%ProgramFiles(x86)%\Python*") do (
    if exist "%%d\python.exe" (
        set "PYTHON_PATH=%%d"
        set "PYTHON_FOUND=1"
    )
)

if defined PYTHON_FOUND (
    set "PATH=!PYTHON_PATH!;!PYTHON_PATH!\Scripts;%PATH%"
    goto run_py
)

REM --- ONLY SHOW BOOTSTRAPPER UI IF PYTHON IS MISSING ---
echo ==========================================================
echo   TriggerCursor Python Bootstrapper for Windows
echo ==========================================================
echo.
echo Python is not installed. We will attempt to install Python 3.
where winget >nul 2>&1
if %errorlevel% equ 0 (
    echo [Bootstrapper] Installing Python via winget...
    winget install --id Python.Python.3 -h --accept-source-agreements --accept-package-agreements
    if !errorlevel! equ 0 (
        echo [Bootstrapper] Python installed successfully via winget.
        REM Retrieve the path of the newly installed Python
        for /d %%d in ("%USERPROFILE%\AppData\Local\Programs\Python\Python*") do (
            if exist "%%d\python.exe" (
                set "PYTHON_PATH=%%d"
            )
        )
        if defined PYTHON_PATH (
            set "PATH=!PYTHON_PATH!;!PYTHON_PATH!\Scripts;%PATH%"
            goto run_py
        )
    )
)

echo [Bootstrapper] Downloading Python installer...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe' -OutFile '%temp%\python-installer.exe'"
if exist "%temp%\python-installer.exe" (
    echo [Bootstrapper] Running Python installer silently...
    start /wait "" "%temp%\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_doc=0 Include_pip=1
    del "%temp%\python-installer.exe"
    
    REM Search for the newly installed path
    for /d %%d in ("%USERPROFILE%\AppData\Local\Programs\Python\Python*") do (
        if exist "%%d\python.exe" (
            set "PYTHON_PATH=%%d"
        )
    )
    if defined PYTHON_PATH (
        echo [Bootstrapper] Python installed and path configured dynamically.
        set "PATH=!PYTHON_PATH!;!PYTHON_PATH!\Scripts;%PATH%"
    ) else (
        echo [Bootstrapper] Python installer completed, but path could not be auto-detected.
        echo Please close this window and run run.bat again.
        pause
        exit /b 1
    )
) else (
    echo [Bootstrapper] Error: Failed to download Python.
    echo Please install Python manually from https://python.org
    pause
    exit /b 1
)

:run_py
REM Move to the script's directory
cd /d "%~dp0"
python run.py %*
if %errorlevel% neq 0 (
    echo.
    echo [TriggerCursor Launcher] Python execution returned error code %errorlevel%.
    pause
)


