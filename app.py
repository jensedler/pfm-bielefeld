"""Web-App: stellt die exportierten Passantenfrequenzdaten zum Download bereit.

Liest ausschließlich aus DATA_DIR (im Container /storage/data); den Abruf
übernimmt scheduler.py. Keine Datenbank — die CSV-Dateien sind der Bestand.
"""

import csv
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import markdown
from flask import Flask, abort, render_template, send_from_directory

PROJEKT_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", PROJEKT_DIR / "data"))

# Nur diese Dateien sind herunterladbar (kein state.json, keine Tmp-Dateien)
DOWNLOAD_MUSTER = re.compile(
    r"^(stationen\.csv|erfassungsbereiche\.geojson|tageswerte\.csv"
    r"|datenqualitaet\.md|komplett\.zip"
    r"|stundenwerte/stundenwerte_\d{4}-\d{2}\.csv)$"
)

app = Flask(__name__)


def lade_state() -> dict:
    try:
        return json.loads((DATA_DIR / "state.json").read_text())
    except (OSError, ValueError):
        return {}


def datei_eintrag(relpfad: str, titel: str, beschreibung: str) -> dict | None:
    pfad = DATA_DIR / relpfad
    if not pfad.exists():
        return None
    groesse = pfad.stat().st_size
    if groesse >= 1024 * 1024:
        anzeige = f"{groesse / 1024 / 1024:.1f} MB"
    else:
        anzeige = f"{max(1, round(groesse / 1024))} kB"
    return {"pfad": relpfad, "titel": titel, "beschreibung": beschreibung,
            "groesse": anzeige}


def chart_daten(tage: int = 30) -> dict | None:
    """Summe aller Erfassungsbereiche pro Tag für die letzten n Tage,
    aufbereitet als Koordinaten für das Inline-SVG."""
    pfad = DATA_DIR / "tageswerte.csv"
    if not pfad.exists():
        return None
    summen: dict[str, int] = {}
    with open(pfad) as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)
        for zeile in reader:
            tag = zeile[3][:10]
            summen[tag] = summen.get(tag, 0) + int(zeile[4])
    if not summen:
        return None
    reihe = [(t, summen[t]) for t in sorted(summen)[-tage:]]

    breite, hoehe = 720, 220
    rand_l, rand_r, rand_o, rand_u = 60, 10, 12, 26
    plot_b, plot_h = breite - rand_l - rand_r, hoehe - rand_o - rand_u
    y_max = max(w for _, w in reihe)
    # y-Achse auf eine runde Obergrenze bringen
    schritt = 10 ** (len(str(y_max)) - 1)
    y_ende = ((y_max // schritt) + 1) * schritt

    punkte = []
    for i, (tag, wert) in enumerate(reihe):
        x = rand_l + (plot_b * i / max(1, len(reihe) - 1))
        y = rand_o + plot_h * (1 - wert / y_ende)
        d = date.fromisoformat(tag)
        punkte.append({
            "x": round(x, 1), "y": round(y, 1), "wert": wert,
            "datum": d.strftime("%d.%m.%Y"),
            "kurz": d.strftime("%d.%m."),
        })
    y_ticks = [{"wert": f"{int(y_ende * f):,}".replace(",", "."),
                "y": round(rand_o + plot_h * (1 - f), 1)}
               for f in (0, 0.5, 1)]
    x_tick_indizes = list(range(0, len(punkte), 7))
    # Letzten Tag nur beschriften, wenn er nicht mit dem Vorgänger kollidiert
    if x_tick_indizes and len(punkte) - 1 - x_tick_indizes[-1] >= 4:
        x_tick_indizes.append(len(punkte) - 1)
    return {
        "punkte": punkte,
        "pfad": " ".join(f"{'M' if i == 0 else 'L'}{p['x']},{p['y']}"
                         for i, p in enumerate(punkte)),
        "y_ticks": y_ticks,
        "x_ticks": [punkte[i] for i in x_tick_indizes],
        "breite": breite, "hoehe": hoehe,
        "plot": {"x": rand_l, "y": rand_o, "b": plot_b, "h": plot_h},
    }


def render_markdown(pfad: Path) -> str:
    return markdown.markdown(pfad.read_text(), extensions=["tables"])


@app.get("/up")
def up():
    """Healthcheck für ONCE. Meldet Fehler, wenn der tägliche Abruf seit
    mehreren Tagen nicht mehr erfolgreich war."""
    state = lade_state()
    datenstand = state.get("datenstand")
    if datenstand and date.fromisoformat(datenstand) < date.today() - timedelta(days=3):
        return "Datenabruf veraltet", 503
    return "OK"


@app.get("/")
def index():
    state = lade_state()
    dateien = [d for d in [
        datei_eintrag("komplett.zip", "Kompletter Datensatz (ZIP)",
                      "Alle nachfolgenden Dateien inkl. Datensatzbeschreibung"),
        datei_eintrag("stationen.csv", "Erfassungsbereiche (CSV)",
                      "Liste der Messbereiche mit Lage, Fläche und Sensoranzahl"),
        datei_eintrag("erfassungsbereiche.geojson", "Erfassungsbereiche (GeoJSON)",
                      "Polygone der Messbereiche für Karten-/GIS-Software"),
        datei_eintrag("tageswerte.csv", "Tageswerte (CSV)",
                      "Passantenfrequenz pro Erfassungsbereich und Tag seit 28.07.2024"),
        datei_eintrag("datenqualitaet.md", "Datenqualitätsbericht (Markdown)",
                      "Vollständigkeit und bekannte Lücken je Monat"),
    ] if d]
    monate = sorted(
        (datei_eintrag(f"stundenwerte/{p.name}",
                       p.stem.removeprefix("stundenwerte_"), "")
         for p in (DATA_DIR / "stundenwerte").glob("stundenwerte_*.csv")),
        key=lambda d: d["titel"], reverse=True,
    ) if (DATA_DIR / "stundenwerte").exists() else []

    beschreibung = ""
    if (PROJEKT_DIR / "DATENSATZBESCHREIBUNG.md").exists():
        beschreibung = render_markdown(PROJEKT_DIR / "DATENSATZBESCHREIBUNG.md")

    return render_template(
        "index.html", state=state, dateien=dateien, monate=monate,
        chart=chart_daten(), beschreibung=beschreibung,
        erzeugt=datetime.now().strftime("%d.%m.%Y %H:%M"),
    )


@app.get("/datenqualitaet")
def datenqualitaet():
    pfad = DATA_DIR / "datenqualitaet.md"
    if not pfad.exists():
        abort(404)
    return render_template("markdown.html", titel="Datenqualität",
                           inhalt=render_markdown(pfad))


@app.get("/impressum")
def impressum():
    return render_template("markdown.html", titel="Impressum",
                           inhalt=render_markdown(PROJEKT_DIR / "impressum.md"))


@app.get("/datenschutz")
def datenschutz():
    return render_template("markdown.html", titel="Datenschutzerklärung",
                           inhalt=render_markdown(PROJEKT_DIR / "datenschutz.md"))


@app.get("/download/<path:name>")
def download(name: str):
    if not DOWNLOAD_MUSTER.match(name):
        abort(404)
    return send_from_directory(DATA_DIR, name, as_attachment=True)
