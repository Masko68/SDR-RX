"""Non-invasive diagnostic for optional decoder programs; does not execute any binary."""
from __future__ import annotations
import shutil
from pathlib import Path
from .decoder_catalog import DECODERS


def main():
    root = Path(__file__).resolve().parent.parent / 'decoders' / 'bin'
    print('SDR Studio RX by M@rcello v0.4 -- EXTERNE DECODERS')
    print('Zoeken in', root, 'en in PATH. Programma\'s worden NIET gestart.\n')
    names = list(dict.fromkeys(d.executable for d in DECODERS if d.executable))
    for name in names:
        local = next((root / n for n in (name, name + '.exe') if (root / n).is_file()), None)
        path = str(local) if local else shutil.which(name)
        status = 'GEVONDEN' if path else 'ONTBREEKT'
        print(f'{status:10s} {name:18s} {path or "zie README.md"}')
    print('\nGEVONDEN betekent alleen bestand aanwezig, niet dat IQ/spraakdecodering gelukt is.')

if __name__ == '__main__':
    main()
