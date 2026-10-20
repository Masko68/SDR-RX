"""Download verified upstream Windows decoder releases into a portable SDR-RX directory.

This script never changes Windows USB drivers, never elevates privileges, and never
executes downloaded files. Upstream executables are not distributed in the source ZIP.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import struct
import sys
import tempfile
import urllib.request
import zipfile

# Fixed URLs and SHA256 digests from the publishers' GitHub release assets.
# Update only after checking the corresponding upstream release.
DECODERS = [
    dict(name='dsd-neo', exe='dsd-neo.exe', version='v2.11.4',
         url='https://github.com/arancormonk/dsd-neo/releases/download/v2.11.4/dsd-neo-msvc-x86_64-native-v2.11.4.zip',
         sha256='236cc07057a35c0349483f81540ba6e137adcbca950f73830f363649c297dc0c'),
    dict(name='AIS-catcher', exe='AIS-catcher.exe', version='v0.70',
         url='https://github.com/jvde-github/AIS-catcher/releases/download/v0.70/AIS-catcher.x64.zip',
         sha256='e6dca80fd1e09e4ec9a3b676a15c386167e9197d9bffc91bff3d88750227ceef'),
    dict(name='rtl_433', exe='rtl_433.exe', version='25.12',
         url='https://github.com/merbanan/rtl_433/releases/download/25.12/rtl_433-win-x64-25.12.zip',
         sha256='ed42651d2a2a94f6419f7675955bd65449d8247e27822c65c363595b715b7de6'),
    dict(name='direwolf', exe='direwolf.exe', version='1.8.1',
         url='https://github.com/wb2osz/direwolf/releases/download/1.8.1/direwolf-1.8.1-a231971_x86_64.zip',
         sha256='5389257646882f8c86cf598c1d403fd3400fa915ca70b1843cd61cc43656a1fa'),
    dict(name='multimon-ng', exe='multimon-ng.exe', version='1.6.1',
         url='https://github.com/EliasOenal/multimon-ng/releases/download/1.6.1/multimon-ng-win64.zip',
         sha256='115946771798e110c76b9dc40eedf285692c5ac0a37386509586d904d92244a0'),
]
AIRSPY_URL = ('https://github.com/airspy/airspyone_host/releases/download/v1.0.10/'
              'airspy_host_tools_win32_x86_x64_v1_0_10.zip')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, output: Path, expected_sha256: str | None = None):
    if not url.startswith('https://github.com/'):
        raise ValueError('Alleen officiële GitHub-release-URL toegestaan')
    request = urllib.request.Request(url, headers={'User-Agent': 'SDRStudioRX-WindowsInstaller/1.0'})
    with urllib.request.urlopen(request, timeout=90) as response, open(output, 'wb') as dst:
        if not response.url.startswith('https://'):
            raise RuntimeError('Onveilige omleiding naar HTTP geweigerd')
        total = 0
        while chunk := response.read(256 * 1024):
            total += len(chunk)
            if total > 120 * 1024 * 1024:
                raise ValueError('Release-archief onverwacht groot')
            dst.write(chunk)
    digest = sha256_file(output)
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        output.unlink(missing_ok=True)
        raise RuntimeError(f'SHA256 verschilt! verwacht {expected_sha256} ontvangen {digest}')
    return digest


def safe_unzip(path: Path, dest: Path):
    """Extract only regular files, never following archive paths out of dest."""
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        files = archive.infolist()
        if len(files) > 20000 or sum(i.file_size for i in files) > 700 * 1024 * 1024:
            raise ValueError('ZIP limiet overschreden')
        base = dest.resolve()
        for member in files:
            name = member.filename.replace('\\', '/')
            rel = PurePosixPath(name)
            if (rel.is_absolute() or '..' in rel.parts or ':' in name or '\0' in name
                    or name.startswith('//')):
                raise ValueError('Onveilig pad in ZIP: ' + name)
            if member.is_dir():
                continue
            # Ignore links and non-regular Unix files.
            mode = (member.external_attr >> 16) & 0o170000
            if mode not in (0, 0o100000):
                raise ValueError('ZIP bevat een link of een speciaal bestand: ' + name)
            target = dest.joinpath(*rel.parts)
            if not target.resolve().is_relative_to(base):
                raise ValueError('Pad verlaat de doelmap')
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst, length=1024*1024)


def locate_exe(root: Path, exe_name: str):
    choices = (p for p in root.rglob('*.exe') if p.name.lower() == exe_name.lower())
    return next(choices, None)


def install_decoder(entry, target_root: Path, download_dir: Path):
    dest = target_root / entry['name']
    old = locate_exe(dest, entry['exe']) if dest.exists() else None
    if old is not None:
        print(f"[AANWEZIG] {entry['name']}: {old}")
        return old
    with tempfile.TemporaryDirectory(prefix='sdr-decoder-') as work:
        temp = Path(work)
        archive = temp / 'release.zip'
        print(f"[DOWNLOAD] {entry['name']} {entry['version']} ...", flush=True)
        digest = download(entry['url'], archive, entry['sha256'])
        print('[SHA256 OK]', digest)
        safe_unzip(archive, temp/'extract')
        exe = locate_exe(temp/'extract', entry['exe'])
        if not exe:
            raise FileNotFoundError('EXE niet gevonden in officiële release: ' + entry['exe'])
        dest.mkdir(parents=True, exist_ok=True)
        # Keep the original directory structure and adjacent DLL dependencies.
        shutil.copytree(temp/'extract', dest, dirs_exist_ok=True)
        installed = locate_exe(dest, entry['exe'])
        if not installed:
            raise RuntimeError('Installatie onverwacht onvolledig')
        print(f"[GEÏNSTALLEERD] {installed}")
        return installed


def pe_architecture(path: Path):
    """Read the PE machine field without loading or executing the DLL."""
    with path.open('rb') as file:
        if file.read(2) != b'MZ': return None
        file.seek(0x3c)
        position = struct.unpack('<I', file.read(4))[0]
        if position > path.stat().st_size - 6: return None
        file.seek(position)
        if file.read(4) != b'PE\0\0': return None
        return struct.unpack('<H', file.read(2))[0]


def install_airspy(drivers: Path):
    """Install an x64 Airspy library plus its same-folder x64 DLL dependencies.

    Airspy's official Windows Host Tools v1.0.10 ZIP calls the library
    ``airspy.dll`` (NOT ``libairspy.dll``). Both names are accepted by
    ``sdr_studio.airspy_native.library_candidates``.
    """
    dll_names = {'airspy.dll', 'libairspy.dll'}
    for name in ('airspy.dll', 'libairspy.dll'):
        candidate = drivers / name
        if candidate.is_file() and pe_architecture(candidate) == 0x8664:
            print('[AANWEZIG] Airspy x64 DLL:', candidate)
            return True

    print('[DOWNLOAD] Airspy Host Tools v1.0.10 (officiele release, geen gepubliceerde SHA256) ...')
    with tempfile.TemporaryDirectory(prefix='sdr-airspy-') as work:
        temp = Path(work)
        archive = temp/'airspy.zip'
        print('[SHA256 downloadbewijs] ' + download(AIRSPY_URL, archive))
        safe_unzip(archive, temp/'extract')
        variants = [p for p in (temp/'extract').rglob('*')
                    if p.is_file() and p.name.lower() in dll_names
                    and pe_architecture(p) == 0x8664]
        if not variants:
            print('[LET OP] Geen x64 airspy.dll of libairspy.dll in officieel archief gevonden.')
            return False
        # Prefer the official x64 directory and avoid the adjacent 32-bit DLLs.
        variants.sort(key=lambda p: (
            0 if any(part.lower() in ('x64', 'amd64', 'win64') for part in p.parts) else 1,
            0 if p.name.lower() == 'airspy.dll' else 1,
            len(p.parts)))
        chosen = variants[0]
        drivers.mkdir(parents=True, exist_ok=True)
        copied = []
        # Copy only x64 DLLs from the SAME x64 directory as the chosen library.
        for other in chosen.parent.iterdir():
            if other.is_file() and other.suffix.lower() == '.dll' and pe_architecture(other) == 0x8664:
                destination = drivers / other.name
                if destination.exists():
                    if sha256_file(destination) != sha256_file(other):
                        print('[CONFLICT] Bestaande DLL wijkt af, niet overschreven:', destination)
                        return False
                else:
                    shutil.copy2(other, destination)
                copied.append(destination)
        target = drivers / chosen.name
        if not target.is_file() or pe_architecture(target) != 0x8664:
            print('[FOUT] Airspy x64 DLL ontbreekt na kopieren.')
            return False
        print('[AIRSPY x64]', target)
        for dep in copied:
            if dep != target:
                print('  dependency:', dep.name)
        return True


def main(argv=None):
    cli=argparse.ArgumentParser(description='SDR Studio RX officiële decoder Windows installer')
    cli.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    cli.add_argument('--airspy',action='store_true',help='Download ook officiële Airspy host DLLs (geen upstream SHA256)')
    cli.add_argument('--allow-partial',action='store_true',help='Bouw door indien sommige decoders ontbreken')
    cli.add_argument('--list',action='store_true',help='Toon overzicht zonder downloads')
    args=cli.parse_args(argv)
    root=args.root.resolve()
    if args.list:
        for e in DECODERS:print(e['name'],e['version'],e['url'])
        print('Airspy:',AIRSPY_URL)
        return 0
    if os.name!='nt':
        print('WAARSCHUWING: officieel voor Windows; deze omgeving kan geen Windows EXE testen.')
    dest=root/'decoders'/'bin'
    dest.mkdir(parents=True,exist_ok=True)
    failed=[]
    for entry in DECODERS:
        try:
            install_decoder(entry,dest,root)
        except Exception as exc:
            failed.append(entry['name'])
            print('[MISLUKT]',entry['name'],type(exc).__name__+':',exc,file=sys.stderr)
    if args.airspy:
        try:
            if not install_airspy(root/'drivers'):failed.append('Airspy x64 DLL')
        except Exception as exc:
            failed.append('Airspy x64 DLL')
            print('[MISLUKT] Airspy:',exc,file=sys.stderr)
    print('\n=== INSTALLATIERAPPORT ===')
    print(f'{len(DECODERS)-sum(e["name"] in failed for e in DECODERS)}/{len(DECODERS)} optionele decoders geïnstalleerd')
    for entry in DECODERS:
        path=locate_exe(dest/entry['name'],entry['exe'])
        print(f' {"OK" if path else "ONTBREEKT"}: {entry["name"]} - {path or entry["url"]}')
    if failed:
        print('Niet beschikbaar:',', '.join(failed))
        print('Handmatige extra tools: dump1090, redsea, acarsdec, WSJT-X, fldigi, SSTV en andere gespecialiseerde modes.')
        return 0 if args.allow_partial else 1
    print('Klaar. Ontvangen/decoderen moet op echte hardware worden getest.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
