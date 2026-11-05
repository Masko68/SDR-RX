# Mykola 20 VFO Scanner v1.3.2

Zelfstandige Windows-scanner met één Airspy R2; **20 VFO's worden na elkaar gescand**, geen 20 fysieke tuners. Dit is geen aanpassing van `Mykola.exe`.

## Nieuwe functies v1.3.2
- **WAV-opname AAN/UIT** kan tijdens het scannen worden omgezet; de lopende WAV wordt netjes afgesloten.
- Duidelijke **REC**-status, laatste WAV-bestand en knop **Open opnamemap**.
- Audio-status blijft correct bij gedempt kanaal.
- Bestaande instellingen, filters, Auto SQ, prioriteit, scanvertraging en echte AM/NFM-audio blijven ongewijzigd.

## Windows starten
1. Pak het Windows-pakket uit in een nieuwe map.
2. Kopieer desgewenst je eigen `data/vfo20.json` uit je vorige werkende versie.
3. Start `START-WINDOWS.bat` (Python 3.11–3.14, 64-bit).
4. Zet **Simulatie** uit voor echte Airspy-ontvangst; gebruik de bij je hardware passende drivers.
5. Zet tijdens de scan **WAV OPNAME AAN/UIT** aan voor het volgende ontvangen gesprek. De opname begint niet zonder open squelch.
6. Klik **Open opnamemap** om de lokale WAV's te bekijken.

## Testen
`python -m unittest discover -s tests -v`

31 automatische tests geslaagd, inclusief live opname aan/uit met de gesimuleerde ontvanger; de echte Airspy R2-hardware moet nog worden getest.

Opnames en logs worden lokaal bewaard en horen niet in de openbare GitHub-repository. Respecteer toepasselijke regels over radiocommunicatie en privacy.

## Windows EXE bouwen

Dubbelklik `BOUW-EXE-WINDOWS.bat`; het bouwt een `dist/Mykola20VFO_v1.3.2.exe` voor Windows 64-bit. 
De bestaande Airspy DLL-bestanden worden in een lokaal gebouwde EXE opgenomen. Configuratie en opnames staan naast de EXE (niet in een tijdelijke PyInstaller-map).
