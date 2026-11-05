@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Mykola 20 VFO v1.3.2 - Windows EXE bouwen
set "LOG=%~dp0exe-bouw-log.txt"
set "VENV=%~dp0.venv_exe"
set "PY=%VENV%\Scripts\python.exe"
>"%LOG%" echo Mykola Windows 64-bit EXE bouw

echo =====================================================
echo   MYKOLA 20 VFO v1.3.2 - EXE BUILDER (Windows)
echo =====================================================
echo Bouwt een zelfstandige EXE, inclusief Python-onderdelen.
echo Internet is nodig om PyInstaller te installeren.
echo.
set "PYCMD=py -3.14"
%PYCMD% -c "import sys" >nul 2>&1
if errorlevel 1 set "PYCMD=python"
%PYCMD% -c "import sys" >nul 2>&1
if errorlevel 1 (
    echo FOUT: Python 3.14 niet gevonden; zie exe-bouw-log.txt.
    >>"%LOG%" echo Python niet gevonden.
    goto :failed
)
%PYCMD% -c "import sys,struct; assert struct.calcsize('P')==8, 'Alleen 64-bit Python'; assert sys.version_info[:2] >= (3,11), 'Python 3.11+ vereist'" >>"%LOG%" 2>&1
if errorlevel 1 goto :failed
if not exist "%PY%" (
    echo [1/4] Python-omgeving maken...
    %PYCMD% -m venv "%VENV%" >>"%LOG%" 2>&1
    if errorlevel 1 goto :failed
)
echo [2/4] Benodigde pakketten controleren/installeren...
"%PY%" -m pip install -r requirements.txt "pyinstaller>=6.22.3,<7" >>"%LOG%" 2>&1
if errorlevel 1 goto :failed

echo [3/4] Softwaretests uitvoeren...
"%PY%" -m unittest discover -s tests -q >>"%LOG%" 2>&1
if errorlevel 1 goto :failed

echo [4/4] Mykola20VFO_v1.3.2.exe maken...
set "BINARGS="
for %%F in (airspy.dll libusb-1.0.dll msvcr100.dll pthreadVC2.dll) do (
    if exist "drivers\%%F" (
        set "BINARGS=!BINARGS! --add-binary drivers\%%F;drivers"
    ) else (
        echo LET OP: drivers\%%F ontbreekt; mogelijk alleen simulatie.
        >>"%LOG%" echo Ontbrekende DLL: %%F
    )
)
"%PY%" -m PyInstaller --noconfirm --clean --onefile --windowed --name "Mykola20VFO_v1.3.2" --collect-all "sounddevice" !BINARGS! app.py >>"%LOG%" 2>&1
if errorlevel 1 goto :failed

echo.
echo GELUKT. Je EXE staat in:
echo   %~dp0dist\Mykola20VFO_v1.3.2.exe
echo Bewaar deze in een eigen schrijfbare map, bijvoorbeeld op je bureaublad.
echo Je frequentielijst, logs en WAV's komen naast de EXE te staan.
echo Let op: Windows kan bij een niet-ondertekende eigen EXE een waarschuwing tonen.
echo.
pause
exit /b 0
:failed
echo.
echo BOUW MISLUKT. Lees exe-bouw-log.txt en stuur mij dat logbestand.
if exist "%LOG%" type "%LOG%"
echo.
pause
exit /b 1
