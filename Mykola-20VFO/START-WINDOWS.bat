@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Mykola 20 VFO - Audiofix en startcontrole
set "LOG=%~dp0start-log.txt"
set "VENV=%~dp0.venv_20vfo"
set "VPY=%VENV%\Scripts\python.exe"
> "%LOG%" echo Mykola 20 VFO - startcontrole
>> "%LOG%" echo Projectmap: %CD%
>> "%LOG%" echo Datum: %DATE% %TIME%

echo ==================================================
echo   MYKOLA 20 VFO v1.1 - SQ/SCANNER FIX PYTHON 3.14
echo ==================================================
echo Deze opdracht toont ook waarom starten mogelijk mislukt.
echo Het oude Mykola-programma wordt niet aangepast.
echo.

rem Probeer expliciet Python 3.14, zonder afhankelijk te zijn van bestandsassociaties.
set "PYCMD=py -3.14"
%PYCMD% -c "import sys" >nul 2>&1
if not errorlevel 1 goto found_python
set "PYCMD=python"
%PYCMD% -c "import sys" >nul 2>&1
if not errorlevel 1 goto found_python
set "PYCMD=py -3"
%PYCMD% -c "import sys" >nul 2>&1
if not errorlevel 1 goto found_python
>> "%LOG%" echo FOUT: Python is niet bereikbaar via py of python.
echo FOUT: Geen Python gevonden. Controleer Python-installatie en PATH.
goto failed

:found_python
echo [1/5] Gevonden Python:
%PYCMD% -c "import sys,platform; print(sys.version);print('Python:',sys.executable);print('Architectuur:',platform.architecture()[0])" >> "%LOG%" 2>&1
%PYCMD% --version
%PYCMD% -c "import sys,struct,tkinter; assert sys.version_info >= (3,11), 'Minstens Python 3.11 vereist'; assert struct.calcsize('P') == 8, 'Python moet 64-bit zijn'; print('Tkinter OK')" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo Python-architectuur of Tkinter niet geschikt. Zie start-log.txt.
  goto failed
)

echo [2/5] Virtuele Python-omgeving controleren ...
if not exist "%VPY%" (
  echo Nieuwe omgeving maken ...
  %PYCMD% -m venv "%VENV%" >> "%LOG%" 2>&1
  if errorlevel 1 goto failed
)
"%VPY%" -c "import sys; print('Venv:',sys.version);print(sys.executable)" >> "%LOG%" 2>&1
if errorlevel 1 goto failed

echo [3/5] Python-pakketten controleren ...
"%VPY%" -c "import numpy,scipy,sounddevice; print('Alle pakketten aanwezig')" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo Pakketten installeren. Voortgang en details staan in start-log.txt.
  "%VPY%" -m pip install -r requirements.txt >> "%LOG%" 2>&1
  if errorlevel 1 goto failed
)

echo [4/5] Startcontrole uitvoeren ...
"%VPY%" -c "import tkinter,numpy,scipy,sounddevice; import config,scanner,radio,dsp,app; print('Importcontrole OK')" >> "%LOG%" 2>&1
if errorlevel 1 goto failed

echo [5/5] App starten ...
echo Scanner gestart: controleer TEST GELUID, SIMULATIE en je Airspy.
echo Bij geluidsproblemen: stuur scanner-log.txt mee.
>> "%LOG%" echo GUI wordt gestart
"%VPY%" app.py >> "%LOG%" 2>&1
set "EXITCODE=%ERRORLEVEL%"
>> "%LOG%" echo GUI afgesloten met exitcode %EXITCODE%
if not "%EXITCODE%"=="0" goto failed

echo.
echo Mykola 20 VFO is gesloten. Er werd geen Python-fout gemeld.
echo Logboek: "%LOG%"
pause
exit /b 0

:failed
echo.
echo STARTEN NIET GELUKT. Het opdrachtvenster blijft open.
echo Open het bestand start-log.txt in dezelfde map om te zien wat er misgaat.
echo.
if exist "%LOG%" type "%LOG%"
echo.
pause
exit /b 1
