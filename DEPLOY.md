# Deployment über ONCE

Die App erfüllt die ONCE-Anforderungen: Docker-Image, HTTP auf Port 80,
Healthcheck unter `/up`, persistente Daten unter `/storage`.

## Image bauen und veröffentlichen

Lokal wird auf Apple Silicon (arm64) entwickelt, der Zielserver ist x86_64 —
daher immer multi-arch bauen:

```sh
docker buildx build --platform linux/amd64,linux/arm64 \
  -t <registry>/datenexport-ariadne:latest --push .
```

## In ONCE installieren

1. Auf dem Server `once` starten, neue App anlegen, als Image
   `<registry>/datenexport-ariadne:latest` und die gewünschte Domain angeben
   (DNS-A-Record muss auf den Server zeigen).
2. In den App-Einstellungen (`s`) die Umgebungsvariablen setzen:

   | Variable | Wert |
   |---|---|
   | `ARIADNE_USERNAME` | API-Benutzername |
   | `ARIADNE_PASSWORD` | API-Passwort |
   | `ARIADNE_LOCATION_ID` | `77` |

3. App starten. Beim ersten Start lädt der Scheduler den kompletten
   Datenbestand seit Messbeginn (ca. 15–20 Minuten); die Seite ist sofort
   erreichbar und zeigt so lange einen Hinweis. Danach läuft täglich um
   05:30 ein inkrementeller Abruf des Vortags.

## Betrieb

- **Persistenz/Backup:** Alle Daten liegen unter `/storage/data` und sind
  damit Teil der ONCE-Backups. Es gibt keine Datenbank — die CSV-Dateien
  sind der Bestand, `state.json` hält den Abrufstatus.
- **Healthcheck:** `/up` liefert 503, wenn der letzte erfolgreiche Abruf
  mehr als 3 Tage zurückliegt — so fällt ein dauerhaft hängender Abruf im
  ONCE-Dashboard auf.
- **Reparatur:** Eine gelöschte Monatsdatei unter
  `/storage/data/stundenwerte/` wird beim nächsten Lauf automatisch neu
  abgerufen; `state.json` löschen erzwingt keinen Neuabruf (der Bestand
  selbst steuert die Inkrementalität).

## Lokal testen

```sh
docker build -t datenexport-ariadne .
docker run -p 8099:80 \
  -e ARIADNE_USERNAME=… -e ARIADNE_PASSWORD=… -e ARIADNE_LOCATION_ID=77 \
  -v ariadne-storage:/storage datenexport-ariadne
```

Ohne Docker: `.venv` anlegen, `pip install -r requirements.txt`, dann
`flask --app app run` (nutzt `./data` und `.env` aus dem Projektordner).
