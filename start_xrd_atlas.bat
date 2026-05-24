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
    echo Python 3.11 or newer with Tcl/Tk was not found.
    echo Install or repair Python 3.11+, then run this file again.
    echo You can also use dist\XRD Atlas\XRD Atlas.exe if it has been built.
    pause
    exit /b 1
)

set "PYTHONUTF8=1"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

"%PYTHON_EXE%" %PYTHON_ARGS% -c "import xrd_atlas.gui" >nul 2>nul
if errorlevel 1 (
    echo Installing XRD Atlas dependencies. Please wait...
    "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -e .
)

"%PYTHON_EXE%" %PYTHON_ARGS% -c "import xrd_atlas.gui" >nul 2>nul
if errorlevel 1 (
    echo.
    echo XRD Atlas dependencies are still not available.
    echo Try this command in PowerShell:
    echo   "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -e .
    pause
    exit /b 1
)

"%PYTHON_EXE%" %PYTHON_ARGS% -m xrd_atlas.gui %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo XRD Atlas failed to start.
    echo Try repairing Python Tcl/Tk, or use dist\XRD Atlas\XRD Atlas.exe.
    pause
)

exit /b %EXIT_CODE%

:try_python
set "CANDIDATE_EXE=%~1"
set "CANDIDATE_ARGS=%~2"
set "CANDIDATE_BASE="
set "CANDIDATE_TCL="
set "CANDIDATE_TK="

"%CANDIDATE_EXE%" %CANDIDATE_ARGS% -c "import sys; raise SystemExit(0 if sys.version_info[:2].__ge__((3, 11)) else 1)" >nul 2>nul
if errorlevel 1 exit /b 0

for /f "delims=" %%B in ('"%CANDIDATE_EXE%" %CANDIDATE_ARGS% -c "import sys; print(sys.base_prefix)" 2^>nul') do set "CANDIDATE_BASE=%%B"
if defined CANDIDATE_BASE (
    if exist "%CANDIDATE_BASE%\tcl\tcl8.6\init.tcl" set "CANDIDATE_TCL=%CANDIDATE_BASE%\tcl\tcl8.6"
    if exist "%CANDIDATE_BASE%\tcl\tk8.6\tk.tcl" set "CANDIDATE_TK=%CANDIDATE_BASE%\tcl\tk8.6"
)
if defined CANDIDATE_TCL set "TCL_LIBRARY=%CANDIDATE_TCL%"
if defined CANDIDATE_TK set "TK_LIBRARY=%CANDIDATE_TK%"

"%CANDIDATE_EXE%" %CANDIDATE_ARGS% -c "import tkinter as tk; root = tk.Tk(); root.destroy()" >nul 2>nul
if errorlevel 1 exit /b 0

set "PYTHON_EXE=%CANDIDATE_EXE%"
set "PYTHON_ARGS=%CANDIDATE_ARGS%"
set "PYTHON_BASE=%CANDIDATE_BASE%"
exit /b 0
