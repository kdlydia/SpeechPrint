@echo off
REM SpeechPrint - Windows launcher
REM
REM Mirrors the Linux/macOS launcher:
REM   No args   -> opens the Qt GUI  (python -m lib.main)
REM   Args      -> forwards to the CLI (python -m lib.cli)
REM
REM Locates Python in this order:
REM   1. %SPEECHPRINT_ROOT%\.venv\Scripts\python.exe (post-installer)
REM   2. %USERPROFILE%\SpeechPrint\.venv\Scripts\python.exe (default install)
REM   3. %LOCALAPPDATA%\Programs\Python\Python311\python.exe
REM   4. py -3.11
REM   5. python

setlocal EnableExtensions EnableDelayedExpansion

set "SPEECHPRINT_LAUNCHER_DIR=%~dp0"
REM Strip trailing backslash
if "%SPEECHPRINT_LAUNCHER_DIR:~-1%"=="\" set "SPEECHPRINT_LAUNCHER_DIR=%SPEECHPRINT_LAUNCHER_DIR:~0,-1%"

if exist "%SPEECHPRINT_LAUNCHER_DIR%\speechprint-config.json" (
    set "SPEECHPRINT_ROOT=%SPEECHPRINT_LAUNCHER_DIR%"
) else (
    echo Error: speechprint-config.json not found 1>&2
    echo Expected at: %SPEECHPRINT_LAUNCHER_DIR%\speechprint-config.json 1>&2
    exit /b 1
)

set "PYTHONPATH=%SPEECHPRINT_ROOT%;%SPEECHPRINT_ROOT%\lib;%PYTHONPATH%"

REM ---------------------------------------------------------------- find python
set "PY="

if exist "%SPEECHPRINT_ROOT%\.venv\Scripts\python.exe" (
    set "PY=%SPEECHPRINT_ROOT%\.venv\Scripts\python.exe"
    goto :have_py
)
if exist "%USERPROFILE%\SpeechPrint\.venv\Scripts\python.exe" (
    set "PY=%USERPROFILE%\SpeechPrint\.venv\Scripts\python.exe"
    goto :have_py
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :have_py
)
if exist "%ProgramFiles%\Python311\python.exe" (
    set "PY=%ProgramFiles%\Python311\python.exe"
    goto :have_py
)

where py >nul 2>&1
if not errorlevel 1 (
    set "PY=py -3.11"
    goto :have_py
)

where python >nul 2>&1
if not errorlevel 1 (
    set "PY=python"
    goto :have_py
)

echo Error: No Python found. 1>&2
echo Run the installer or install Python 3.11+ first. 1>&2
exit /b 1

:have_py

REM ------------------- if launching the GUI, sanity-check PyQt6 ---------------
if "%~1"=="" (
    %PY% -c "import PyQt6" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('SpeechPrint cannot find PyQt6.`n`nRun the installer first (double-click SpeechPrint.bat, choose Install SpeechPrint), or install manually:`n`n    %PY% -m pip install PyQt6', 'SpeechPrint', 'OK', 'Warning')" >nul 2>&1
        echo Error: PyQt6 not installed for %PY% 1>&2
        exit /b 1
    )
    %PY% -m lib.main
    exit /b %errorlevel%
) else (
    %PY% -m lib.cli %*
    exit /b %errorlevel%
)
