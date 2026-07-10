"""Täglicher Datenabruf für die Web-App.

Läuft als eigener Prozess neben Gunicorn (siehe entrypoint.sh): holt beim
Start alle fehlenden Daten (erster Start = kompletter Backfill), danach
täglich morgens den Vortag. Schreibt den Status nach DATA_DIR/state.json
und baut nach jedem erfolgreichen Lauf das Download-ZIP.

Aufruf mit --einmal für einen einzelnen Lauf ohne Endlosschleife.
"""

import json
import sys
import time
import traceback
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import export
from export import DATA_DIR, PROJEKT_DIR, schreibe_atomar

ABRUF_STUNDE = 5  # täglicher Lauf um 05:30 lokaler Zeit
ABRUF_MINUTE = 30


def schreibe_state(**felder) -> None:
    try:
        state = json.loads((DATA_DIR / "state.json").read_text())
    except (OSError, ValueError):
        state = {}
    state.update(felder)
    schreibe_atomar(DATA_DIR / "state.json", json.dumps(state, indent=1))


def baue_zip() -> None:
    """Packt den kompletten Datensatz in ein ZIP (atomar ersetzt)."""
    ziel = DATA_DIR / "komplett.zip"
    tmp = ziel.with_suffix(".zip.tmp")
    dateien = [
        DATA_DIR / "stationen.csv",
        DATA_DIR / "erfassungsbereiche.geojson",
        DATA_DIR / "tageswerte.csv",
        DATA_DIR / "datenqualitaet.md",
        PROJEKT_DIR / "DATENSATZBESCHREIBUNG.md",
        *sorted((DATA_DIR / "stundenwerte").glob("stundenwerte_*.csv")),
    ]
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for datei in dateien:
            if datei.exists():
                arcname = (f"stundenwerte/{datei.name}"
                           if datei.parent.name == "stundenwerte" else datei.name)
                z.write(datei, f"passantenfrequenzen-bielefeld/{arcname}")
    tmp.replace(ziel)
    print(f"ZIP gebaut ({ziel.stat().st_size / 1024 / 1024:.1f} MB).")


def lauf() -> None:
    start = datetime.now().isoformat(timespec="seconds")
    schreibe_state(letzter_lauf=start)
    try:
        export.main()
        baue_zip()
        schreibe_state(
            letzter_erfolg=datetime.now().isoformat(timespec="seconds"),
            datenstand=(date.today() - timedelta(days=1)).isoformat(),
            fehler=None,
        )
    except BaseException as e:  # auch SystemExit aus export.py abfangen
        if isinstance(e, KeyboardInterrupt):
            raise
        print(f"Abruf fehlgeschlagen: {e}")
        traceback.print_exc()
        schreibe_state(fehler=str(e))


def sekunden_bis_naechstem_lauf() -> float:
    jetzt = datetime.now()
    naechster = jetzt.replace(hour=ABRUF_STUNDE, minute=ABRUF_MINUTE,
                              second=0, microsecond=0)
    while naechster <= jetzt:
        naechster += timedelta(days=1)
    return (naechster - jetzt).total_seconds()


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lauf()
    if "--einmal" in sys.argv:
        sys.exit(0)
    while True:
        wartezeit = sekunden_bis_naechstem_lauf()
        print(f"Nächster Abruf in {wartezeit / 3600:.1f} h.")
        time.sleep(wartezeit)
        lauf()
