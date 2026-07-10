# CLAUDE.md — Kontext für KI-Agents

## Worum es geht

Beantwortung der IFG-Anfrage #369610 (fragdenstaat.de) zu Passantenfrequenzdaten
der Bielefelder Innenstadt (Messsystem: Ariadne Maps, Smartphone-Tracking per
Multilateration in ~40 Erfassungspolygonen). Die App ruft täglich die
Ariadne-API ab und stellt CSV/GeoJSON-Downloads bereit. Aufgabenstand und
offene Punkte: `PLAN.md`.

## Architektur (bewusst minimal)

- **Keine Datenbank.** Die CSV-Dateien unter `data/` (Container: `/storage/data`)
  sind der Datenbestand; `state.json` hält nur den Abrufstatus.
- `export.py` — Abruflogik inkl. aller API-Workarounds; nutzbar als CLI und
  als Modul. Inkrementell: vollständige Vergangenheitsmonate werden übersprungen,
  eine gelöschte Monatsdatei wird automatisch neu geholt.
- `scheduler.py` — eigener Prozess neben Gunicorn (siehe `entrypoint.sh`);
  Backfill beim Erststart, danach täglich 05:30 Uhr; baut nach jedem Lauf
  `komplett.zip`. `--einmal` für Einzellauf.
- `app.py` — Flask, eine Download-Seite + `/datenqualitaet` + `/up` + Downloads
  über Allowlist-Regex. Diagramm ist server-gerendertes Inline-SVG.
- Deployment: ONCE-kompatibel (Port 80, `/up`, `/storage`), Release über
  `v*`-Tag → GitHub Actions → `ghcr.io/jensedler/pfm-bielefeld`. Details: `DEPLOY.md`.

## API-Eigenheiten (hart erarbeitet — nicht „vereinfachen")

Basis `https://api.ariadne.inc/api/v2`, Login per Basic Auth → JWT (~1 Jahr).
Credentials: lokal `.env`, im Container Env-Variablen (`ARIADNE_*`), Location-ID 77.

1. **Randstunden-Bug:** Bei Abfragen mit exakten Zeitraumgrenzen fehlen Stunden
   des ersten/letzten Tages → immer mit ±1 Tag Überlappung abrufen und filtern
   (`hole_werte`).
2. **Stille Kürzung:** Große CSV-Antworten werden mitten im Datenstrom
   abgeschnitten, ohne Fehler → Abruf in 10-Tage-Chunks und Prüfung, dass der
   letzte angefragte Tag in der Antwort vorkommt; sonst Wiederholung.
3. Vereinzelte Verbindungs-Timeouts sind normal → Retries mit Backoff, nicht
   als Blocker werten.
4. `format=csv` wird nicht paginiert (`page` → 400); JSON wäre paginiert.
5. `passersby` ist für Bielefeld nicht konfiguriert (400) — es gibt nur `visitors`.
6. Tageswert = Summe der Stundenwerte (verifiziert), keine Tages-Deduplizierung.

## Datenbesonderheiten

- Messbeginn 2024-07-28. Wöchentliche Lücke Fr 23:00 (Wartungsfenster).
- Sept 2024: paralleler Satz generisch benannter Areas („Niederwall 1" …) —
  nur in diesem Monat, räumlich überlappend mit den regulären Bereichen.
- Fehlende Stunde 02:00 an DST-Frühjahrs-Umstellungstagen ist korrekt (Lokalzeit).
- Bereichszuschnitte ändern sich über die Zeit; `datenqualitaet.md` listet
  Abdeckungszeiträume (wird bei jedem Lauf neu erzeugt).

## Rote Linien

- **Gerätebezogene Endpoints (`optin`, `optin-raw`, `optin-visit`, `trajectory`)
  niemals abrufen oder veröffentlichen** — Entscheidung von Jens, 10.07.2026.
  Nur aggregierte Zählwerte sind Teil dieses Projekts.
- `Input/` enthält Credentials und personenbezogene Daten (IFG-Anfrage) und ist
  gitignored — nie committen, nie ins Image kopieren.

## Konventionen

- Sprache in Code-Kommentaren, Doku und UI: Deutsch. Jens wird geduzt.
- Python stdlib bevorzugen; Web-Abhängigkeiten minimal (Flask, gunicorn, Markdown).
- Alle Dateien im Datenbestand atomar schreiben (`schreibe_atomar`).
- Falls je eine Datenbank nötig wird: SQLite.

## Lokal arbeiten

```sh
python3 export.py                    # Abruf/Backfill nach ./data (nutzt .env)
python3 scheduler.py --einmal        # Einzellauf inkl. ZIP + state.json
.venv/bin/flask --app app run        # Web-App gegen ./data
```

Docker-Test: siehe `DEPLOY.md` (Abschnitt „Lokal testen").
