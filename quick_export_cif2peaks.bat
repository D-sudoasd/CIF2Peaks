@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE="
set "PYTHON_ARGS="
set "PYTHON_BASE="

if exist ".venv\Scripts\python.exe" (
    call :try_python ".venv\Scripts\python.exe" ""
)

if not defined PYTHON_EXE (
    py -3.11 --version >nul 2>nul
    if not errorlevel 1 call :try_python "py" "-3.11"
)

if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        if not defined PYTHON_EXE call :try_python "%%P" ""
    )
)

if not defined PYTHON_EXE (
    echo Python 3.11 or newer was not found.
    echo Install Python 3.11+, or use dist\CIF2Peaks\CIF2Peaks.exe if it has been built.
    pause
    exit /b 1
)

if "%~1"=="" (
    echo Drag one or more .cif files, or a folder containing CIF files, onto this file.
    pause
    exit /b 1
)

set "PYTHONUTF8=1"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

"%PYTHON_EXE%" %PYTHON_ARGS% -c "import cif2peaks.quick_export" >nul 2>nul
if errorlevel 1 (
    echo Installing CIF2Peaks dependencies. Please wait...
    "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -e .
)

"%PYTHON_EXE%" %PYTHON_ARGS% -m cif2peaks.quick_export %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Done. The Excel file was saved next to the first CIF file.
) else (
    echo Quick export failed. You can still use start_cif2peaks.bat for the GUI workflow.
)
pause
exit /b %EXIT_CODE%

:try_python
set "CANDIDATE_EXE=%~1"
set "CANDIDATE_ARGS=%~2"
set "CANDIDATE_BASE="

"%CANDIDATE_EXE%" %CANDIDATE_ARGS% -c "import sys; raise SystemExit(0 if sys.version_info[:2].__ge__((3, 11)) else 1)" >nul 2>nul
if errorlevel 1 exit /b 0

for /f "delims=" %%B in ('"%CANDIDATE_EXE%" %CANDIDATE_ARGS% -c "import sys; print(sys.base_prefix)" 2^>nul') do set "CANDIDATE_BASE=%%B"
if defined CANDIDATE_BASE (
    if exist "%CANDIDATE_BASE%\tcl\tcl8.6\init.tcl" set "TCL_LIBRARY=%CANDIDATE_BASE%\tcl\tcl8.6"
    if exist "%CANDIDATE_BASE%\tcl\tk8.6\tk.tcl" set "TK_LIBRARY=%CANDIDATE_BASE%\tcl\tk8.6"
)

set "PYTHON_EXE=%CANDIDATE_EXE%"
set "PYTHON_ARGS=%CANDIDATE_ARGS%"
set "PYTHON_BASE=%CANDIDATE_BASE%"
exit /b 0
