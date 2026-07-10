#!/usr/bin/env python3
"""Exportiert Passantenfrequenzdaten aus der Ariadne-API nach data/.

Erzeugt:
  data/stationen.csv                        Liste der Erfassungsbereiche (Messstationen)
  data/erfassungsbereiche.geojson           Polygone der Erfassungsbereiche
  data/tageswerte.csv                       Tageswerte je Erfassungsbereich seit Messbeginn
  data/stundenwerte/stundenwerte_YYYY-MM.csv  Stundenwerte je Erfassungsbereich, monatsweise
  data/datenqualitaet.md                    Bericht über Lücken im Datenbestand

Das Skript ist inkrementell: vollständige Vergangenheitsmonate werden nicht erneut
abgerufen. Löschen einer Monatsdatei erzwingt den Neuabruf. Zugangsdaten kommen
aus der Umgebung oder aus .env (ARIADNE_USERNAME, ARIADNE_PASSWORD,
ARIADNE_LOCATION_ID).

Bewusst NICHT abgerufen werden Endpoints mit gerätebezogenen Daten
(optin, optin-raw, optin-visit, trajectory).
"""

import calendar
import csv
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE_URL = "https://api.ariadne.inc/api/v2"
MESSBEGINN = date(2024, 7, 28)
PROJEKT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJEKT_DIR / "data"
STUNDEN_DIR = DATA_DIR / "stundenwerte"
CSV_HEADER = "location;ID;area;date;visitors"
RETRIES = 4


def lade_config() -> dict:
    env_datei = PROJEKT_DIR / ".env"
    if env_datei.exists():
        for zeile in env_datei.read_text().splitlines():
            zeile = zeile.strip()
            if zeile and not zeile.startswith("#") and "=" in zeile:
                key, _, wert = zeile.partition("=")
                os.environ.setdefault(key.strip(), wert.strip())
    try:
        return {
            "username": os.environ["ARIADNE_USERNAME"],
            "password": os.environ["ARIADNE_PASSWORD"],
            "location_id": os.environ["ARIADNE_LOCATION_ID"],
        }
    except KeyError as e:
        sys.exit(f"Fehlende Konfiguration: {e} (in .env oder Umgebung setzen)")


def http_get(url: str, headers: dict | None = None) -> bytes:
    letzte_ausnahme: Exception = RuntimeError("unreachable")
    for versuch in range(RETRIES):
        try:
            anfrage = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(anfrage, timeout=300) as antwort:
                return antwort.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            letzte_ausnahme = e
            wartezeit = 5 * (versuch + 1)
            print(f"  Anfrage fehlgeschlagen ({e}), neuer Versuch in {wartezeit}s …")
            time.sleep(wartezeit)
    raise SystemExit(f"Abbruch: API nicht erreichbar ({letzte_ausnahme})")


def login(config: dict) -> str:
    import base64

    auth = base64.b64encode(
        f"{config['username']}:{config['password']}".encode()
    ).decode()
    daten = http_get(f"{BASE_URL}/login", {"Authorization": f"Basic {auth}"})
    token = json.loads(daten).get("token")
    if not token:
        raise SystemExit(f"Login fehlgeschlagen: {daten[:200]!r}")
    return token


def api_get(pfad: str, token: str, **params) -> bytes:
    params["token"] = token
    query = urllib.parse.urlencode(params)
    return http_get(f"{BASE_URL}/{pfad}?{query}")


def pruefe_csv(daten: bytes, kontext: str) -> str:
    text = daten.decode("utf-8-sig")
    if not text.startswith(CSV_HEADER):
        raise SystemExit(
            f"Unerwartete Antwort bei {kontext}: {text[:200]!r}"
        )
    return text


def export_stationen(token: str, location_id: str) -> None:
    print("Exportiere Stationsliste und Geometrie …")
    parents = json.loads(api_get(f"locations/{location_id}/parents", token))
    devices = json.loads(api_get(f"locations/{location_id}/devicearea", token))

    sensoren_je_area: dict[str, int] = {}
    for geraet in devices.get("data", []):
        area = geraet.get("areas")
        if area:
            sensoren_je_area[area] = sensoren_je_area.get(area, 0) + 1

    features = []
    for ebene in parents.get("geometry", []):
        features.extend(ebene.get("geometry", {}).get("features", []))
    geojson = {"type": "FeatureCollection", "features": features}
    (DATA_DIR / "erfassungsbereiche.geojson").write_text(
        json.dumps(geojson, ensure_ascii=False, indent=1)
    )

    with open(DATA_DIR / "stationen.csv", "w", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(
            ["bereich", "erfassungsbereich", "quartier", "flaeche_qm",
             "anzahl_sensoren", "lat_min", "lat_max", "lng_min", "lng_max"]
        )
        for feature in sorted(
            features, key=lambda x: (x["properties"].get("parent_1", ""),
                                     x["properties"].get("name", ""))
        ):
            p = feature["properties"]
            koords = p.get("min_max_coords", {})
            w.writerow([
                p.get("parent_1", ""),
                p.get("name", ""),
                p.get("parent_2", ""),
                p.get("geodesic_area", ""),
                sensoren_je_area.get(p.get("name", ""), 0),
                koords.get("lat_min", ""), koords.get("lat_max", ""),
                koords.get("lng_min", ""), koords.get("lng_max", ""),
            ])
    print(f"  {len(features)} Erfassungsbereiche geschrieben.")


def monatsende(jahr: int, monat: int) -> date:
    return date(jahr, monat, calendar.monthrange(jahr, monat)[1])


def export_tageswerte(token: str, location_id: str, bis: date) -> None:
    """Tageswerte monatsweise abrufen (der Gesamtzeitraum in einem Request
    überfordert die API) und zu einer Gesamtdatei zusammensetzen."""
    cache_dir = DATA_DIR / "tageswerte_monate"
    cache_dir.mkdir(exist_ok=True)
    teile = []
    jahr, monat = MESSBEGINN.year, MESSBEGINN.month
    while (jahr, monat) <= (bis.year, bis.month):
        start = max(date(jahr, monat, 1), MESSBEGINN)
        ende = min(monatsende(jahr, monat), bis)
        datei = cache_dir / f"tageswerte_{jahr}-{monat:02d}.csv"
        if not (ende == monatsende(jahr, monat) and monat_vollstaendig(datei, ende)):
            print(f"Exportiere Tageswerte {jahr}-{monat:02d} ({start} bis {ende}) …")
            daten = api_get(
                f"locations/{location_id}/areas/visitors", token,
                start=start.isoformat(), end=ende.isoformat(),
                step="day", format="csv",
            )
            datei.write_text(pruefe_csv(daten, f"Tageswerten {jahr}-{monat:02d}"))
        teile.append(datei)
        jahr, monat = (jahr + 1, 1) if monat == 12 else (jahr, monat + 1)

    with open(DATA_DIR / "tageswerte.csv", "w") as gesamt:
        gesamt.write(CSV_HEADER + "\n")
        for datei in teile:
            inhalt = datei.read_text().splitlines()[1:]
            gesamt.write("\n".join(inhalt) + ("\n" if inhalt else ""))
    zeilen = sum(1 for _ in open(DATA_DIR / "tageswerte.csv")) - 1
    print(f"  tageswerte.csv mit {zeilen} Datenzeilen geschrieben.")


def monat_vollstaendig(datei: Path, ende: date) -> bool:
    """Prüft, ob die Monatsdatei Daten bis zum letzten Tag des Monats enthält."""
    if not datei.exists():
        return False
    letzte_zeile = datei.read_text().rstrip().rsplit("\n", 1)[-1]
    teile = letzte_zeile.split(";")
    return len(teile) == 5 and teile[3].startswith(ende.isoformat())


def export_stundenwerte(token: str, location_id: str, bis: date) -> None:
    STUNDEN_DIR.mkdir(exist_ok=True)
    jahr, monat = MESSBEGINN.year, MESSBEGINN.month
    while (jahr, monat) <= (bis.year, bis.month):
        start = max(date(jahr, monat, 1), MESSBEGINN)
        ende = min(monatsende(jahr, monat), bis)
        datei = STUNDEN_DIR / f"stundenwerte_{jahr}-{monat:02d}.csv"
        if ende == monatsende(jahr, monat) and monat_vollstaendig(datei, ende):
            print(f"Stundenwerte {jahr}-{monat:02d}: vollständig, übersprungen.")
        else:
            print(f"Exportiere Stundenwerte {jahr}-{monat:02d} ({start} bis {ende}) …")
            # Mit einem Tag Überlappung an beiden Rändern abrufen: startet oder
            # endet der Zeitraum exakt an der Bereichsgrenze, unterschlägt die
            # API die ersten bzw. letzten Stunden des Randtages.
            daten = api_get(
                f"locations/{location_id}/areas/visitors", token,
                start=(start - timedelta(days=1)).isoformat(),
                end=(ende + timedelta(days=1)).isoformat(),
                step="hour", format="csv",
            )
            text = pruefe_csv(daten, f"Stundenwerten {jahr}-{monat:02d}")
            zeilen = [z for z in text.splitlines()[1:]
                      if start.isoformat() <= z.split(";")[3][:10] <= ende.isoformat()]
            datei.write_text(CSV_HEADER + "\n" + "\n".join(zeilen) + "\n")
            print(f"  {len(zeilen)} Datenzeilen geschrieben.")
        jahr, monat = (jahr + 1, 1) if monat == 12 else (jahr, monat + 1)


def erzeuge_qualitaetsbericht(bis: date) -> None:
    print("Erzeuge Datenqualitätsbericht …")
    zeilen = [
        "# Datenqualität Stundenwerte",
        "",
        f"Automatisch erzeugt am {date.today().isoformat()}. "
        f"Zeitraum: {MESSBEGINN} bis {bis}.",
        "",
        "Fehlende Stunden sind Zeiträume, für die die Ariadne-API keinen Wert"
        " liefert (z. B. Systemausfall oder Wartung). Stunden mit dem Wert 0"
        " gelten als vorhanden.",
        "",
        "| Monat | Erfassungsbereiche | vorhandene Stunden | erwartete Stunden | fehlend | systemweit fehlende Stunden |",
        "|---|---|---|---|---|---|",
    ]
    for datei in sorted(STUNDEN_DIR.glob("stundenwerte_*.csv")):
        with open(datei) as f:
            reader = csv.reader(f, delimiter=";")
            next(reader, None)
            areas, stunden_gesamt = set(), {}
            for zeile in reader:
                areas.add(zeile[2])
                stunden_gesamt[zeile[3]] = stunden_gesamt.get(zeile[3], 0) + 1
        tage = {stunde[:10] for stunde in stunden_gesamt}
        erwartet = len(areas) * len(tage) * 24
        vorhanden = sum(stunden_gesamt.values())
        # Stunden, die bei keiner einzigen Area vorkommen, an erfassten Tagen
        alle_stunden = {f"{tag} {h:02d}:00:00" for tag in tage for h in range(24)}
        systemweit_fehlend = sorted(alle_stunden - set(stunden_gesamt))
        beispiel = (", ".join(s[:13] for s in systemweit_fehlend[:5])
                    + (" …" if len(systemweit_fehlend) > 5 else ""))
        zeilen.append(
            f"| {datei.stem.removeprefix('stundenwerte_')} | {len(areas)} "
            f"| {vorhanden} | {erwartet} | {erwartet - vorhanden} "
            f"| {len(systemweit_fehlend)}{': ' + beispiel if beispiel else ''} |"
        )
    (DATA_DIR / "datenqualitaet.md").write_text("\n".join(zeilen) + "\n")


def main() -> None:
    config = lade_config()
    DATA_DIR.mkdir(exist_ok=True)
    gestern = date.today() - timedelta(days=1)
    token = login(config)
    print("Login erfolgreich.")
    export_stationen(token, config["location_id"])
    export_tageswerte(token, config["location_id"], gestern)
    export_stundenwerte(token, config["location_id"], gestern)
    erzeuge_qualitaetsbericht(gestern)
    print("Fertig.")


if __name__ == "__main__":
    main()
