"""Reproducible, conservative Windows onedir build for SDR Studio RX.

This build keeps the entire app and downloaded third-party decoders but
excludes heavyweight optional Qt stacks and pytest from PyInstaller.
It uses the fresh `.venv-slim` created by MAAK_KLEINE_WINDOWS_VERSIE.bat.

Do NOT remove Qt DLLs manually from the final distribution: PyInstaller's
binary dependency analysis has to remain authoritative.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NAME = 'SDR-Studio-RX-SLIM'
ENTRY = ROOT / '_build_tools' / 'sdr_rx_entry_slim.py'

# Source app only uses QtCore/QtGui/QtWidgets; 2D pyqtgraph doesn't use OpenGL.
# SciPy signal modules and the SDR/PortAudio native bindings are retained.
EXCLUDED_MODULES = (
    'pytest',
    'pyqtgraph.opengl',
    'IPython',
    'matplotlib',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngineQuick',
    'PySide6.QtPdf',
    'PySide6.QtPdfWidgets',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuickWidgets',
    'PySide6.Qt3DCore',
    'PySide6.Qt3DRender',
    'PySide6.QtTest',
)

ENTRY_CONTENT = '''"""SDR Studio RX -- portable build entry point."""
import sys

if '--slim-selftest' in sys.argv:
    # Offscreen Qt widget test without SDR hardware or a visible desktop.
    from PySide6 import QtCore, QtGui, QtWidgets
    import pyqtgraph as pg
    import numpy as np
    from scipy import signal
    import sounddevice
    app = QtWidgets.QApplication([])
    widget = pg.PlotWidget()
    widget.plot(np.asarray([0.0, 1.0, 0.0]))
    if signal.sosfilt(signal.butter(2, .1, output='sos'), [0.0, 1.0]).size != 2:
        raise AssertionError('SciPy signal ontbreekt')
    widget.close()
    print('SLIM_SELFTEST_OK')
    raise SystemExit(0)

from sdr_studio.app import main
if __name__ == '__main__':
    main()
'''


def build_command() -> list[str]:
    """Single source of truth for local Windows BAT and GitHub Actions."""
    cmd = [
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--onedir', '--console', '--contents-directory', '.',
        '--name', NAME, '--paths', str(ROOT),
        # Keep native RTL-SDR, USB, PortAudio libraries and their metadata.
        '--collect-all', 'rtlsdr',
        '--collect-all', 'pyrtlsdrlib',
        '--collect-all', '_sounddevice_data',
    ]
    for module in EXCLUDED_MODULES:
        cmd.extend(('--exclude-module', module))
    cmd.append(str(ENTRY))
    return cmd


def copy_portable_parts(dst: Path) -> None:
    """Keep decoder companion DLLs and Airspy drivers in their own directories."""
    for relative in ('decoders/bin', 'drivers'):
        source = ROOT / relative
        target = dst / relative
        target.mkdir(parents=True, exist_ok=True)
        if source.exists():
            shutil.copytree(source, target, dirs_exist_ok=True)
    docs = dst / 'docs'
    docs.mkdir(exist_ok=True)
    for file in ('WINDOWS_COMPLETE_HANDLEIDING.md', 'DERDEN_LICENTIES_EN_DOWNLOADS.md'):
        src = ROOT / 'docs' / file
        if src.is_file():
            shutil.copy2(src, docs / file)
    for source, dest in (
        ('CONTROLEER_WINDOWS_PAKKET.bat', 'CONTROLEER_WINDOWS_PAKKET.bat'),
        ('LICENSE', 'LICENSE-SDR-RX.txt'),
    ):
        if (ROOT / source).is_file():
            shutil.copy2(ROOT / source, dst / dest)


def smoke_test(executable: Path) -> None:
    env = os.environ.copy()
    env['QT_QPA_PLATFORM'] = 'offscreen'
    try:
        result = subprocess.run(
            [str(executable), '--slim-selftest'],
            cwd=executable.parent, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', timeout=65,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('EXE selftest duurde langer dan 65 seconden') from exc
    print(result.stdout)
    if result.returncode != 0 or 'SLIM_SELFTEST_OK' not in result.stdout:
        raise RuntimeError('Ingepakte EXE faalt Qt/pyqtgraph/SciPy/PortAudio selftest')


def main() -> int:
    if sys.platform != 'win32':
        print('[FOUT] Windows EXE kan alleen op Windows worden gebouwd.')
        return 1
    if not (ROOT / 'sdr_studio' / 'app.py').is_file():
        print('[FOUT] Plaats de bouwer in de SDR-RX projecthoofdmap.')
        return 1
    ENTRY.parent.mkdir(exist_ok=True)
    ENTRY.write_text(ENTRY_CONTENT, encoding='utf-8')
    print('[SLIM] PyInstaller: alleen noodzakelijke Qt-, DSP- en SDR-modules...', flush=True)
    subprocess.run(build_command(), cwd=ROOT, check=True)
    out = ROOT / 'dist' / NAME
    exe = out / (NAME + '.exe')
    if not exe.is_file():
        raise FileNotFoundError(f'PyInstaller-uitvoer ontbreekt: {exe}')
    copy_portable_parts(out)
    print('[SLIM] Automatische EXE-starttest (zonder SDR-hardware)...', flush=True)
    smoke_test(exe)
    print('[SLIM] EXE en volledige portable map GEREED: ' + str(exe))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print('[FOUT] SLIM bouwen of testen mislukt: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
