@echo off
setlocal
cd /d "%~dp0"

set "REPORT_PATH=%CD%\xrd_atlas_self_test_report.txt"
> "%REPORT_PATH%" echo XRD Atlas Windows self-test report
>> "%REPORT_PATH%" echo Created: %DATE% %TIME%
>> "%REPORT_PATH%" echo XRD Atlas folder: %CD%
>> "%REPORT_PATH%" echo Windows version:
ver >> "%REPORT_PATH%"
>> "%REPORT_PATH%" echo Processor architecture: %PROCESSOR_ARCHITECTURE%
>> "%REPORT_PATH%" echo.

call :log "XRD Atlas Windows self-test"
call :log ""
call :log "Report saved to: %REPORT_PATH%"
call :log ""

if not exist "XRD Atlas.exe" (
    call :log "Missing XRD Atlas.exe"
    goto fail
)
call :log "Found XRD Atlas.exe"

if not exist "XRD Atlas Quick Export.exe" (
    call :log "Missing XRD Atlas Quick Export.exe"
    goto fail
)
call :log "Found XRD Atlas Quick Export.exe"

if not exist "_internal\_tcl_data\init.tcl" (
    call :log "Missing packaged Tcl files."
    goto fail
)
call :log "Found packaged Tcl files."

if not exist "_internal\_tk_data\tk.tcl" (
    call :log "Missing packaged Tk files."
    goto fail
)
call :log "Found packaged Tk files."

if not exist "examples\cif" (
    call :log "Missing example CIF files."
    goto fail
)
call :log "Found example CIF files."

set "XRD_ATLAS_SMOKE_TEST=1"

call :log "Checking GUI startup..."
start /wait "" "%CD%\XRD Atlas.exe" "%CD%\examples\cif"
if errorlevel 1 (
    call :log "GUI startup check failed."
    goto fail
)
call :log "GUI startup check passed."

set "TEST_DIR=%TEMP%\xrd_atlas_self_test_%RANDOM%_%RANDOM%"
set "BAD_TEST_DIR="
mkdir "%TEST_DIR%" >nul 2>nul
if errorlevel 1 (
    call :log "Could not create temporary test folder."
    goto fail
)
call :log "Created temporary test folder: %TEST_DIR%"

copy /Y "examples\cif\*.cif" "%TEST_DIR%\" >nul
> "%TEST_DIR%\bad.cif" echo data_bad
>> "%TEST_DIR%\bad.cif" echo _cell_length_a 3

call :log "Checking quick export..."
start /wait "" "%CD%\XRD Atlas Quick Export.exe" "%TEST_DIR%"
if errorlevel 1 (
    call :log "Quick export check failed."
    goto fail_cleanup
)

dir /b "%TEST_DIR%\*.xlsx" >nul 2>nul
if errorlevel 1 (
    call :log "Quick export did not create an Excel workbook."
    goto fail_cleanup
)

set "OUTPUT_XLSX="
for %%F in ("%TEST_DIR%\*.xlsx") do (
    if not defined OUTPUT_XLSX set "OUTPUT_XLSX=%%~fF"
)
if not defined OUTPUT_XLSX (
    call :log "Could not locate generated Excel workbook."
    goto fail_cleanup
)
call :log "Generated workbook: %OUTPUT_XLSX%"

call :log "Checking generated workbook content..."
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.IO.Compression.FileSystem; $zip=[IO.Compression.ZipFile]::OpenRead($env:OUTPUT_XLSX); try { function ReadZipText($name) { $entry=$zip.GetEntry($name); if ($null -eq $entry) { throw ('Missing workbook part: ' + $name) }; $reader=[System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8); try { return $reader.ReadToEnd() } finally { $reader.Dispose() } }; $guide=[System.Text.RegularExpressions.Regex]::Unescape('\u4f7f\u7528\u8bf4\u660e'); $beginner=[System.Text.RegularExpressions.Regex]::Unescape('\u63a8\u8350\u5cf0\u8868'); $friendly=[System.Text.RegularExpressions.Regex]::Unescape('CIF \u683c\u5f0f\u4e0d\u5b8c\u6574\u6216\u65e0\u6cd5\u89e3\u6790\u3002\u8bf7\u68c0\u67e5\u8be5\u6587\u4ef6\u662f\u5426\u5305\u542b\u6676\u80de\u53c2\u6570\u548c\u539f\u5b50\u5750\u6807\u3002'); $workbook=ReadZipText 'xl/workbook.xml'; $summary=ReadZipText 'xl/worksheets/sheet1.xml'; $quote=[char]34; if (-not $workbook.Contains('name=' + $quote + $guide + $quote)) { throw 'Missing guide sheet.' }; if (-not $workbook.Contains('name=' + $quote + $beginner + $quote)) { throw 'Missing beginner peak sheet.' }; if (-not $summary.Contains($friendly)) { throw 'Missing friendly CIF error message.' } } finally { $zip.Dispose() }"
if errorlevel 1 (
    call :log "Generated workbook content check failed."
    goto fail_cleanup
)
call :log "Generated workbook content check passed."

set "BAD_TEST_DIR=%TEMP%\xrd_atlas_bad_cif_test_%RANDOM%_%RANDOM%"
mkdir "%BAD_TEST_DIR%" >nul 2>nul
if errorlevel 1 (
    call :log "Could not create invalid-CIF test folder."
    goto fail_cleanup
)
> "%BAD_TEST_DIR%\bad.cif" echo data_bad
>> "%BAD_TEST_DIR%\bad.cif" echo _cell_length_a 3

call :log "Checking diagnostic workbook for invalid CIF..."
start /wait "" "%CD%\XRD Atlas Quick Export.exe" "%BAD_TEST_DIR%\bad.cif"
if errorlevel 1 (
    call :log "Invalid-CIF diagnostic export failed."
    goto fail_cleanup
)

set "OUTPUT_XLSX="
for %%F in ("%BAD_TEST_DIR%\*.xlsx") do (
    if not defined OUTPUT_XLSX set "OUTPUT_XLSX=%%~fF"
)
if not defined OUTPUT_XLSX (
    call :log "Invalid-CIF diagnostic workbook was not created."
    goto fail_cleanup
)
call :log "Diagnostic workbook: %OUTPUT_XLSX%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.IO.Compression.FileSystem; $zip=[IO.Compression.ZipFile]::OpenRead($env:OUTPUT_XLSX); try { function ReadZipText($name) { $entry=$zip.GetEntry($name); if ($null -eq $entry) { throw ('Missing workbook part: ' + $name) }; $reader=[System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8); try { return $reader.ReadToEnd() } finally { $reader.Dispose() } }; $guide=[System.Text.RegularExpressions.Regex]::Unescape('\u4f7f\u7528\u8bf4\u660e'); $beginner=[System.Text.RegularExpressions.Regex]::Unescape('\u63a8\u8350\u5cf0\u8868'); $friendly=[System.Text.RegularExpressions.Regex]::Unescape('CIF \u683c\u5f0f\u4e0d\u5b8c\u6574\u6216\u65e0\u6cd5\u89e3\u6790\u3002\u8bf7\u68c0\u67e5\u8be5\u6587\u4ef6\u662f\u5426\u5305\u542b\u6676\u80de\u53c2\u6570\u548c\u539f\u5b50\u5750\u6807\u3002'); $workbook=ReadZipText 'xl/workbook.xml'; $summary=ReadZipText 'xl/worksheets/sheet1.xml'; $quote=[char]34; if (-not $workbook.Contains('name=' + $quote + $guide + $quote)) { throw 'Missing guide sheet.' }; if (-not $workbook.Contains('name=' + $quote + $beginner + $quote)) { throw 'Missing beginner peak sheet.' }; if (-not $summary.Contains($friendly)) { throw 'Missing friendly CIF error message.' } } finally { $zip.Dispose() }"
if errorlevel 1 (
    call :log "Invalid-CIF diagnostic workbook content check failed."
    goto fail_cleanup
)
call :log "Invalid-CIF diagnostic workbook content check passed."

call :log ""
call :log "Self-test passed."
rmdir /s /q "%TEST_DIR%" >nul 2>nul
if defined BAD_TEST_DIR rmdir /s /q "%BAD_TEST_DIR%" >nul 2>nul
set "XRD_ATLAS_SMOKE_TEST="
pause
exit /b 0

:fail_cleanup
rmdir /s /q "%TEST_DIR%" >nul 2>nul
if defined BAD_TEST_DIR rmdir /s /q "%BAD_TEST_DIR%" >nul 2>nul

:fail
call :log ""
call :log "Self-test failed. Copy the whole XRD Atlas folder and try again."
call :log "Please send xrd_atlas_self_test_report.txt when asking for help."
set "XRD_ATLAS_SMOKE_TEST="
pause
exit /b 1

:log
if "%~1"=="" (
    echo.
    >> "%REPORT_PATH%" echo.
) else (
    echo %~1
    >> "%REPORT_PATH%" echo %~1
)
exit /b 0
