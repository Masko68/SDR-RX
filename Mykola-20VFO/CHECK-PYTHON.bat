@echo off
setlocal
cd /d "%~dp0"
title Mykola 20 VFO - Diagnose Python 3.14
set "LOG=%~dp0python-check.txt"
> "%LOG%" echo Python en GUI diagnose
>> "%LOG%" echo DATUM: %DATE% %TIME%
echo Python-diagnose wordt gestart ...
where py >> "%LOG%" 2>&1
where python >> "%LOG%" 2>&1
py -0p >> "%LOG%" 2>&1
py -3.14 -c "import sys,struct,tkinter; print(sys.version); print(sys.executable); print('64-bit:',struct.calcsize('P')==8); print('Tk:',tkinter.TkVersion)" >> "%LOG%" 2>&1
python -c "import sys,struct,tkinter; print(sys.version); print(sys.executable); print('64-bit:',struct.calcsize('P')==8); print('Tk:',tkinter.TkVersion)" >> "%LOG%" 2>&1
if exist ".venv_20vfo\Scripts\python.exe" (
  ".venv_20vfo\Scripts\python.exe" -c "import sys,numpy,scipy,sounddevice; print(sys.version);print('NumPy:',numpy.__version__,'SciPy:',scipy.__version__,'Sounddevice:',sounddevice.__version__)" >> "%LOG%" 2>&1
)
echo.
echo Diagnose opgeslagen in python-check.txt
echo.
type "%LOG%"
echo.
pause
