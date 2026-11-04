# Mykola 20 VFO scanner — bewerkbare broncode

Een zelfstandige Windows-scanner voor Airspy R2/Mini met 20 instelbare VFO-regels.
De ontvanger scant ingestelde kanalen **achter elkaar**. Per VFO zijn frequentie, AM/NFM, squelch, mute en volume instelbaar.
Dit is een onafhankelijk prototype, **geen wijziging aan Mykola SDR 1.5.90 FREE** en geen commerciële uitgave.

## Gebruik

- Windows 10/11, Python 3.11+ (getest door gebruiker met Python 3.14, 64-bit).
- Pak de broncode uit en voer `START-WINDOWS.bat` uit.
- De startprocedure installeert afhankelijkheden uit `requirements.txt` in `.venv_20vfo`.
- Met **Simulatie** aan is geen ontvanger nodig; met **Simulatie** uit gebruikt de scanner de Airspy.
- Voor echte ontvangst zijn geschikte Airspy DLL's in `drivers/` vereist. Bekijk `drivers/README.txt`.
- De onafhankelijke per-VFO-instellingen betekenen **niet** dat er 20 hardwaretuners gelijktijdig ontvangen.

## Broncode

- `app.py`: GUI
- `scanner.py`: scanlogica en audio-uitvoer
- `radio.py`: Airspy-koppeling en simulatie
- `dsp.py`: signaalverwerking
- `config.py`: kanaalinstellingen
- `data/vfo20.json`: voorbeeldfrequenties
- `tests/`: automatische tests

## Veilig delen

De DLL's uit de meegeleverde Mykola FREE-distributie en de originele `Mykola.exe` staan **niet** in deze repository. Dit voorkomt het openbaar maken van derde-partij-bestanden zonder afzonderlijke controle van distributierechten. De eigen werkende Windows-map blijft onaangetast.

Er is nog geen expliciete licentie voor de broncode gekozen. Zonder licentie is hergebruik door anderen niet automatisch toegestaan.
