@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE="
set "PYTHON_ARGS="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
)

if not defined PYTHON_EXE (
    py -3.11 --version >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=py"
        set "PYTHON_ARGS=-3.11"
    )
)

if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        if not defined PYTHON_EXE (
            "%%P" -c "import sys; raise SystemExit(0 if sys.version_info[:2].__ge__((3, 11)) else 1)" >nul 2>nul
            if not errorlevel 1 set "PYTHON_EXE=%%P"
        )
    )
)

if not defined PYTHON_EXE (
    echo Python 3.11 or newer was not found.
    echo Install Python 3.11+ first, then run this file again.
    pause
    exit /b 1
)

for /f "delims=" %%P in ('call "%PYTHON_EXE%" %PYTHON_ARGS% -c "import sys; print(sys.base_prefix)" 2^>nul') do set "PYTHON_BASE=%%P"
set "TCL_LIBRARY=%PYTHON_BASE%\tcl\tcl8.6"
set "TK_LIBRARY=%PYTHON_BASE%\tcl\tk8.6"

if not exist "%TCL_LIBRARY%\init.tcl" (
    echo Tcl files were not found at "%TCL_LIBRARY%".
    echo Reinstall Python with Tcl/Tk support, then run this file again.
    pause
    exit /b 1
)

if not exist "%TK_LIBRARY%\tk.tcl" (
    echo Tk files were not found at "%TK_LIBRARY%".
    echo Reinstall Python with Tcl/Tk support, then run this file again.
    pause
    exit /b 1
)

echo Installing Windows packaging tools...
"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -e .[windows]
if errorlevel 1 (
    echo.
    echo Packaging dependencies could not be installed.
    pause
    exit /b 1
)

echo.
echo Building standalone Windows app...
"%PYTHON_EXE%" %PYTHON_ARGS% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --name "CIF2Peaks" ^
    --additional-hooks-dir scripts\pyinstaller_hooks ^
    --exclude-module pytest ^
    --exclude-module numpy.tests ^
    --exclude-module scipy.tests ^
    --runtime-hook scripts\pyi_rth_tkinter.py ^
    --add-data "%TCL_LIBRARY%:_tcl_data" ^
    --add-data "%TK_LIBRARY%:_tk_data" ^
    --add-binary "%PYTHON_BASE%\DLLs\_tkinter.pyd:." ^
    --add-binary "%PYTHON_BASE%\DLLs\tcl86t.dll:." ^
    --add-binary "%PYTHON_BASE%\DLLs\tk86t.dll:." ^
    --collect-all pymatgen ^
    --collect-submodules scipy ^
    --collect-submodules numpy ^
    --collect-submodules tkinter ^
    --hidden-import gemmi ^
    --hidden-import spglib ^
    --hidden-import tkinter ^
    --hidden-import tkinterdnd2 ^
    --hidden-import _tkinter ^
    scripts\cif2peaks_windows.py

if errorlevel 1 (
    echo.
    echo Build failed. See the PyInstaller output above.
    pause
    exit /b 1
)

echo.
echo Building standalone quick export app...
"%PYTHON_EXE%" %PYTHON_ARGS% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --name "CIF2Peaks Quick Export" ^
    --additional-hooks-dir scripts\pyinstaller_hooks ^
    --exclude-module pytest ^
    --exclude-module numpy.tests ^
    --exclude-module scipy.tests ^
    --runtime-hook scripts\pyi_rth_tkinter.py ^
    --add-data "%TCL_LIBRARY%:_tcl_data" ^
    --add-data "%TK_LIBRARY%:_tk_data" ^
    --add-binary "%PYTHON_BASE%\DLLs\_tkinter.pyd:." ^
    --add-binary "%PYTHON_BASE%\DLLs\tcl86t.dll:." ^
    --add-binary "%PYTHON_BASE%\DLLs\tk86t.dll:." ^
    --collect-all pymatgen ^
    --collect-submodules scipy ^
    --collect-submodules numpy ^
    --collect-submodules tkinter ^
    --hidden-import gemmi ^
    --hidden-import spglib ^
    --hidden-import tkinter ^
    --hidden-import tkinterdnd2 ^
    --hidden-import _tkinter ^
    scripts\cif2peaks_quick_export_windows.py

if errorlevel 1 (
    echo.
    echo Quick export build failed. See the PyInstaller output above.
    pause
    exit /b 1
)

if exist "dist\CIF2Peaks Quick Export\CIF2Peaks Quick Export.exe" (
    copy /Y "dist\CIF2Peaks Quick Export\CIF2Peaks Quick Export.exe" "dist\CIF2Peaks\CIF2Peaks Quick Export.exe" >nul
)

echo.
echo Adding portable user files...
copy /Y "README_WINDOWS.txt" "dist\CIF2Peaks\README_WINDOWS.txt" >nul
copy /Y "windows_self_test.bat" "dist\CIF2Peaks\windows_self_test.bat" >nul
if not exist "dist\CIF2Peaks\examples\cif" mkdir "dist\CIF2Peaks\examples\cif"
xcopy /Y /I "examples\cif\*.cif" "dist\CIF2Peaks\examples\cif\" >nul

echo.
echo Creating portable zip...
"%PYTHON_EXE%" %PYTHON_ARGS% scripts\package_windows_portable.py "dist\CIF2Peaks" "dist\CIF2Peaks_Windows_Portable.zip"
if errorlevel 1 (
    echo.
    echo Portable zip packaging failed.
    pause
    exit /b 1
)

echo.
echo Build complete:
echo   dist\CIF2Peaks\CIF2Peaks.exe
echo   dist\CIF2Peaks\CIF2Peaks Quick Export.exe
echo   dist\CIF2Peaks\windows_self_test.bat
echo   dist\CIF2Peaks_Windows_Portable.zip
echo.
echo Send "dist\CIF2Peaks_Windows_Portable.zip" to another Windows computer, unzip it, then run windows_self_test.bat.
pause
