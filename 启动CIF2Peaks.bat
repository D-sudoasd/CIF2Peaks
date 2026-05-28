@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "START_SCRIPT=%PROJECT_DIR%start_cif2peaks.bat"

if not exist "%START_SCRIPT%" (
    echo Cannot find:
    echo   "%START_SCRIPT%"
    echo.
    echo Please keep this launcher in the CIF2Peaks project folder.
    pause
    exit /b 1
)

call "%START_SCRIPT%" %*
exit /b %ERRORLEVEL%
