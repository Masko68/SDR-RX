"""Measure the Windows distribution tree; never delete/modify any DLLs."""
from __future__ import annotations
import argparse
from pathlib import Path

MEGABYTE = 1024 * 1024


def tree_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())


def fmt(value: int) -> str:
    return f'{value/MEGABYTE:,.1f} MB'


def describe(label: str, path: Path) -> int:
    print(f'\n--- {label}: {path} ---')
    if not path.exists():
        print('NIET AANWEZIG')
        return 0
    total = tree_size(path)
    print('Totaal:', fmt(total))
    print('Grootste mappen/bestanden:')
    folders = sorted(((tree_size(p), p.name) for p in path.iterdir()), reverse=True)
    for size, name in folders[:14]:
        print(f'  {fmt(size):>13}  {name}')
    return total


def main(argv=None):
    parser = argparse.ArgumentParser(description='Geen bestanden worden gewijzigd.')
    parser.add_argument('original', type=Path)
    parser.add_argument('slim', type=Path)
    args = parser.parse_args(argv)
    old = describe('VORIGE BUILDMAP', args.original)
    new = describe('NIEUWE SLIM-BUILDMAP', args.slim)
    if old and new:
        diff = old - new
        print(f'\nVerschil: {fmt(abs(diff))} ' + ('kleiner' if diff > 0 else 'groter' if diff < 0 else 'gelijk'))
        print(f'Verandering: {(100*diff/old):.1f}% minder schijfruimte' if diff > 0 else 'Geen netto verkleining')
    print('\nLet op: de ZIP-grootte is niet gelijk aan de uitgepakte programmagrootte.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
