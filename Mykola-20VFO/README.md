# Mykola 20 VFO Scanner — v1.1

Bewerkbare, zelfstandige Windows-scanner met **20 VFO's** voor één Airspy R2/Mini.
De VFO's worden **na elkaar** gescand. Iedere VFO heeft eigen frequentie, AM/NFM,
squelch, volume en mute. Dit project verandert de originele `Mykola.exe` niet.

## Nieuw in v1.1
- Squelch opent pas na twee opeenvolgende positieve metingen (minder valse stops).
- 3 dB hysterese beperkt klapperen bij zwakke signalen.
- Korte audio-voorbuffer bewaart het begin van een gedetecteerd signaal.
- Minder GUI-signaalupdates.
- Knop **AM SQ → -70** voor alle ingeschakelde AM-kanalen.
- De drie voorbeeldkanalen beginnen met -70 dBFS.

## Starten
- Windows 10/11, Python 3.11–3.14 (64-bit).
- Zet compatibele Airspy-DLL's in `drivers/` als je met hardware wilt werken.
  Deze externe DLL's worden **niet** op GitHub meegeleverd.
- Dubbelklik `START-WINDOWS.bat`. Test eerst **TEST GELUID**.
- Zet **Simulatie (zonder hardware)** uit voor echte ontvangst.
- Kopieer eventueel je eigen `data/vfo20.json` uit je vorige installatie
  naar de nieuwe map voordat je de app start.

## Testen
`python -m unittest discover -s tests -v` — 12 tests geslaagd bij oplevering.

**Status:** de gebruikersversie vóór v1.1 gaf echte Airspy-audio; v1.1 is
geautomatiseerd getest, maar nog niet op de echte Airspy R2 gevalideerd.

Geen sublicentie voor Mykola of de externe Airspy-bibliotheken is verleend.
