# Mykola 20 VFO Scanner — v1.2

Bewerkbare, zelfstandige scanner voor Windows 64-bit (Python 3.11–3.14) en Airspy R2/Mini.
**Eén ontvanger scant maximaal 20 ingestelde VFO-frequenties na elkaar**; dit is geen uitbreiding of patch van `Mykola.exe`.

## Nieuw in v1.2

- **Audiofilter:** `Standaard` (origineel v1.1), `Spraak` en `Ruisarm`, AM en NFM.
- **Auto SQ per VFO**, optioneel en standaard uit. Leert achtergrondruis tijdens gesloten squelch en hanteert een instelbare marge (standaard 8 dB); valt terug op de handmatige SQ totdat een rustige meting is gezien.
- Behoud van v1.1: 20 VFO-regels, squelch-hysterese, testaudio, scan-hervatvertraging, CSV import/export en Windows-logbestanden.
- Achterwaartse compatibiliteit met `data/vfo20.json` uit v1.1.

## Installatie

1. Download de *Windows-versie* uit de ChatGPT-projectbestanden en pak hem uit in een nieuwe map.
2. Bewaar de oude v1.1-map. Kopieer indien gewenst je persoonlijke `data/vfo20.json` naar de nieuwe map.
3. Sluit andere programma's die de Airspy gebruiken en dubbelklik op `START-WINDOWS.bat`.
4. Test `TEST GELUID`, schakel simulatie uit voor echte ontvangst, kies een audiofilter en vink `AUTO SQ` aan voor de VFO's die automatische squelch moeten gebruiken.
5. Wijzigingen gaan in na **STOP** en opnieuw **START**.

**Drivers:** de Windows-uitgave bevat de door de gebruiker aangeleverde Airspy-DLL's. Deze broncode-repository bevat *geen* externe DLL's. Plaats op een nieuwe Windows-installatie geschikte libairspy x64-DLL's in `drivers/` volgens `drivers/README.txt`.

## Ontwikkeling en tests

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

20 softwaretests geslaagd bij oplevering. GUI-start gecontroleerd met een virtueel scherm. **Echte Airspy R2-ontvangst in v1.2 moet nog door de gebruiker worden getest**; v1.1 was bij de gebruiker werkend.

Het project is onafhankelijk van Mykola FREE en verleent geen rechten op externe Mykola-bestanden of Airspy-driverbibliotheken.
