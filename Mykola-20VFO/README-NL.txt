20 VFO SCANNER – BEWERKBAAR WINDOWS PROJECT
=============================================

DOEL
- 20 VFO-regels onder elkaar met verticale schuifbalk.
- Per VFO: frequentie (MHz), naam, AM/NFM, squelch (-100...-5 dBFS), volume (0...100), mute, aan/uit.
- Scant VFOs na elkaar met één Airspy R2/Mini; geen 20 gelijktijdige hardware tuners.
- Bij ontvangst opent de eigen squelch en wordt de audio van die VFO afgespeeld.
- Bij einde signaal hervat de scanner na de instelbare hervatvertraging.
- Slaat configuratie op als JSON, inclusief CSV-import/export.
- Starts met drie voorbeeldfrequenties uit de aangeleverde schermafbeelding. De overige 17 zijn leeg/uit.

INSTALLATIE
1. Pak de ZIP uit op een Windows 10/11 PC.
2. Installeer Python 3.11 of nieuwer, 64-bit, met PATH ingeschakeld.
3. Dubbelklik START-WINDOWS.bat. Deze vernieuwde startcontrole maakt .venv_20vfo en schrijft start-log.txt.
4. Start met 'Simulatie (zonder hardware)' voor een eerste test.
5. Sluit Mykola (en SDR#) voordat je het vinkje Simulatie uitzet; Airspy kan doorgaans
   maar door één programma tegelijk worden geopend.
6. Zet het vinkje Simulatie uit, stel de frequenties in, klik START SCAN.
7. Werkt het niet? Controleer de USB-verbinding, Windows audio, Visual C++ x64 runtime,
   en de bibliotheken in de map drivers/.

LET OP
- Dit is GEEN aanpassing van Mykola.exe, en GEEN ontgrendeling van Mykola FREE.
- Deze losstaande implementatie is een eerste, bewerkbare prototypeversie.
- Airspy-hardwareontvangst en geluid zijn hier niet fysiek getest op Windows/Airspy R2;
  de scanner- en DSP-componenten zijn met geautomatiseerde tests gecontroleerd.
- De radio kan grofweg 24...1700 MHz ontvangen (in dit prototype VFO t/m 1699,95 MHz); HF-ontvangst vereist een geschikte converter.
- De eigen squelchwaarde is een geschatte kanaalsterkte in dBFS; afregelen per VFO.
- Gebruik AM voor luchtvaart, NFM voor smalband-FM. Geen DMR/TETRA/DAB-decoders.
- De ondersteunde sample rates worden uit de hardware uitgelezen (2,5 of 10 MSPS).
  Airspy beveelt voor hoge performance 10 MSPS aan; dit vergt meer CPU/USB.
- Eén radiobron wordt achter elkaar omgestemd; actieve VFO kan daardoor andere VFOs
  tijdelijk niet scannen. De per-VFO audio-instellingen zijn onafhankelijk.

AANPASSEN
- app.py        Tkinter lay-out, 20 VFO-regels
- config.py     aantal VFOs (SLOTS=20), JSON configuratie
- scanner.py    scanvolgorde, squelch en audio-uitvoer
- radio.py      Airspy hardware-koppeling en simulatie
- dsp.py        AM/NFM demodulator, signaalmeting
- data/vfo20.json  opgeslagen kanaallijst (ontstaat na Opslaan)
- tests/        tests uitvoeren: python -m unittest discover -s tests -v

AIRSPY-BIBLIOTHEKEN
De Windows DLL-bestanden in drivers/ komen uitsluitend uit het door de gebruiker
geüploade Mykola-archief. Ze zijn niet door de scanner zelf herschreven.
Bij gebruik van een nieuwere officiële Airspy-driver vervang je deze vier DLLs
als set. Zie ook drivers/LICENSE-3RD-PARTY.txt voor licenties/verwijzingen.

BEKEND: ONTWIKKELSTATUS
- Prototype, dus geen officieel Mykola-product.
- Op hardware niet geverifieerd; audio- en RF-prestaties kunnen tuning vergen.
- Gain is de libairspy linearity gain; eerste squelchcheck op -55 dBFS.
- Software werkt met één Airspy R2/Mini; er is geen onafhankelijke radio per VFO.

- Wijzigingen tijdens het scannen worden pas na STOP en START opnieuw ingeladen.

AUDIOFIX - NOVEMBER 2026
========================
- Test de Windows-geluidsuitgang met de knop TEST GELUID voordat je scant.
- Hoor je geen testtoon? Kies in de keuzelijst een andere speakers/headset-uitgang.
- De scanner vermeldt nu expliciet of je in SIMULATIE of via Airspy R2 scant.
- Staat SIMULATIE aan? Je hoort alleen kunstmatige testtoon, GEEN echte gesprekken.
- Voor echte radio: sluit eerst de originele Mykola en SDR#; zet SIMULATIE UIT.
- Start voor luchtvaart bijv. met AM, SQ -90 dBFS, volume 100, mute uit,
  gain ongeveer 10-15; verhoog squelch zodra er signaalsterkte bekend is.
- Een open squelch kan ruis laten horen; een andere ingestelde frequentie
  is niet automatisch een actieve zender.
- Bij geen audio, stuur scanner-log.txt. Daarin staan Airspy, audio en fouten.
- Audioapparaat wordt per project opgeslagen in data/vfo20.json als audio_device.
- Windows-speakeruitgang wordt niet automatisch bepaald als je een specifiek
  audioapparaat selecteert dat later wordt losgekoppeld.
- De individuele VFO-volumes zijn geldig, maar na elkaar (geen 20 parallelle tuners).
- Hardware ontvangst met je Airspy R2 is op jouw Windows-pc nog niet bevestigd.
