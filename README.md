# Passantenfrequenzen Bielefeld (pfm-bielefeld)

Download-Portal für die Passantenfrequenzdaten der Bielefelder Innenstadt
(Messsystem Ariadne Maps, ~40 Erfassungsbereiche, seit 28.07.2024). Die App
ruft täglich die Ariadne-API ab und stellt die Daten als CSV/GeoJSON bereit —
entstanden zur Beantwortung einer IFG-Anfrage (fragdenstaat.de #369610), mit
dem Ziel, die Daten dauerhaft offen verfügbar zu machen.

## Was die App macht

- **Täglicher Abruf** (05:30 Uhr) der Tages- und Stundenwerte des Vortags;
  beim ersten Start automatischer Backfill seit Messbeginn
- **Download-Seite** mit Stationsliste (CSV + GeoJSON-Polygone), Tageswerten,
  Stundenwerten pro Monat, Datenqualitätsbericht und Komplett-ZIP
- **30-Tage-Verlaufsdiagramm** und Statusanzeige des Datenstands
- Beschreibung der Daten und Messmethodik: `DATENSATZBESCHREIBUNG.md`

Keine Datenbank, kein Framework-Frontend: die CSV-Dateien sind der Bestand,
die Seite ist server-gerendertes HTML.

## Betrieb

Docker-Image: `ghcr.io/jensedler/pfm-bielefeld:latest` (multi-arch,
amd64/arm64). Deployment über [ONCE](https://github.com/basecamp/once) —
Anleitung, Env-Variablen und Release-Prozess: **`DEPLOY.md`**.

## Entwicklung

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                 # Zugangsdaten eintragen (falls vorhanden)
python3 export.py                    # Daten nach ./data abrufen
.venv/bin/flask --app app run        # http://127.0.0.1:5000
```

Wichtige Dateien: `export.py` (API-Abruf inkl. Workarounds für
API-Eigenheiten), `scheduler.py` (täglicher Lauf), `app.py` (Web-App).
Kontext für KI-Agents: `CLAUDE.md`.

## Lizenz

Code: GPL-3.0 (siehe `LICENSE`). Lizenz der Daten: wird von Stadt
Bielefeld / WEGE mbH festgelegt.
