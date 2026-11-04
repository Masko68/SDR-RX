# Mykola 20 VFO scanner – v1.3

**Losse, bewerkbare Python-Windows-scanner** voor Airspy R2/Mini, geen wijziging
van het originele commerciële programma Mykola en geen extra VFO-ontgrendeling.

### Functies
- 20 instelbare AM/NFM VFO-regels; **één Airspy stemt ze na elkaar af**.
- Per VFO squelch (handmatig of Auto SQ), volume en mute.
- Audiofilter: Standaard / Spraak / Ruisarm.
- **v1.3**: `Na gesprek (s)` houdt de scanner na een wegvallend signaal 0,1–10 s vast;
  begin met 2 of 3 seconden.
- **v1.3**: optioneel prioriteitskanaal met controle na elke 1–10 normale VFO's.
  Prioriteitscontrole gebeurt **alleen tussen scans / gesprekken**: met één
  ontvanger kan niet gelijktijdig naar een ander kanaal worden geluisterd.
- **v1.3**: optioneel WAV opnemen van squelch-actieve audio, PCM 48 kHz, mono,
  16-bit. WAV wordt in `opnames/` gezet, ook als de luidspreker-MUTE aan staat.
  Opnemen staat standaard **uit**; er wordt niets geüpload naar GitHub.

### Windows-start
1. Pak de Windows-ZIP uit in een **nieuwe** map (bewaar v1.2).
2. Kopieer eventueel je eigen `data/vfo20.json` uit de werkende versie.
3. Dubbelklik `START-WINDOWS.bat` (Python 3.11–3.14, 64-bit).
4. Bij echte ontvangst: andere SDR-software sluiten en `Simulatie` uitvinken.
5. Bij opname: vink **Automatisch WAV opnemen** aan en herstart de scan.

De externe Airspy/USB DLL's worden niet in deze GitHub-broncode opgenomen.
De Windows-versie behoudt de lokaal aangeleverde DLL's. Hardwareontvangst
met v1.3 is nog niet onafhankelijk getest; v1.2 werkte bij de gebruiker.

Gebruik opname en delen van opgenomen communicatie alleen waar dat wettelijk
is toegestaan en met respect voor privacy.

### Broncode en tests
```
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python app.py
```

De **29 automatische tests** (inclusief een gesimuleerde WAV-opname) slagen
op de ontwikkelomgeving. Zie `README-NL.txt` voor de volledige handleiding.
