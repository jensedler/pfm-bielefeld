# Passantenfrequenzen Bielefelder Innenstadt — Datensatzbeschreibung

Messdaten des Passantenfrequenz-Messsystems der Bielefelder Innenstadt
(Anbieter: Ariadne Maps GmbH), bereitgestellt durch die Stadt Bielefeld und
die WEGE mbH anlässlich einer Anfrage nach dem Informationsfreiheitsgesetz
NRW (fragdenstaat.de, Anfrage #369610).

**Zeitraum:** 28.07.2024 (Messbeginn) bis heute, fortlaufend ergänzt
**Räumliche Abdeckung:** rund 40 Erfassungsbereiche in der Bielefelder Innenstadt
**Format:** CSV (Trennzeichen Semikolon, Kodierung UTF-8) bzw. GeoJSON
**Zeitangaben:** lokale Zeit (Europe/Berlin); am Tag der Umstellung auf
Sommerzeit existiert die Stunde 02:00 nicht

## Wie wird gemessen?

Das System des Anbieters Ariadne erfasst anonymisierte Funksignale von
Smartphones über fest installierte Sensoren. Die Position eines Geräts wird
durch das Zusammenspiel mehrerer Sensoren bestimmt (Multilateration) und
einem vordefinierten **Erfassungsbereich** (Polygon, z. B. ein
Straßenabschnitt zwischen bestimmten Hausnummern) zugeordnet.

Das unterscheidet sich grundlegend von klassischen Laser-Zählern:

- **Bereich statt Zähllinie:** Gemessen wird die Präsenz von Geräten in
  einem gesamten Bereich, nicht das Überschreiten einer Linie an einem
  Punkt. Eine „Messstation" im Sinne dieses Datensatzes ist daher ein
  Erfassungsbereich, nicht ein einzelner Sensor.
- **Messwert „visitors":** Anzahl der im jeweiligen Zeitintervall im
  Erfassungsbereich erfassten (anonymisierten) Endgeräte. Der Wert ist eine
  gerätebasierte Näherung der Passantenzahl — Personen ohne erfassbares
  Gerät fehlen, und die Erfassungsquote kann technisch bedingt schwanken.
  Die Werte eignen sich daher vor allem für Vergleiche über Zeit und
  zwischen Bereichen, weniger als absolute Personenzahlen.
- **Tageswert = Summe der Stundenwerte:** Ein Gerät, das in mehreren
  Stunden desselben Tages erfasst wird, geht mehrfach in den Tageswert ein.
- Eine separate Metrik „Vorbeigehende" (passers-by) ist für Bielefeld nicht
  konfiguriert und kann daher nicht bereitgestellt werden.

## Dateien und Spalten

### stationen.csv — Liste der Erfassungsbereiche (aktuelle Konfiguration)

| Spalte | Bedeutung |
|---|---|
| `bereich` | übergeordneter Bereich (Straße/Platz), ggf. leer |
| `erfassungsbereich` | Name des Erfassungsbereichs (Schlüssel zu den Messwertdateien, Spalte `area`) |
| `quartier` | übergeordnetes Quartier, ggf. leer |
| `flaeche_qm` | Fläche des Erfassungspolygons in m² |
| `anzahl_sensoren` | Zahl der aktuell diesem Bereich zugeordneten Sensoren (0 = Bereich wird durch umliegende Sensoren mit abgedeckt) |
| `lat_min` … `lng_max` | Begrenzungsrechteck des Polygons (WGS84) |

### erfassungsbereiche.geojson — Polygone der Erfassungsbereiche

GeoJSON-FeatureCollection (WGS84). Der Bereichsname steht in
`properties.name`, die Zuordnung zu Straße/Platz und Quartier in
`properties.parent_1` und `properties.parent_2`.

### tageswerte.csv — Passantenfrequenz pro Erfassungsbereich und Tag

| Spalte | Bedeutung |
|---|---|
| `location` | immer `bielefeld` |
| `ID` | immer `77` (System-ID der Stadt) |
| `area` | Name des Erfassungsbereichs |
| `date` | Datum (`JJJJ-MM-TT 00:00:00`) |
| `visitors` | erfasste Endgeräte an diesem Tag (Summe der Stundenwerte) |

### stundenwerte/stundenwerte_JJJJ-MM.csv — Passantenfrequenz pro Stunde

Gleiche Spalten wie `tageswerte.csv`; `date` enthält die volle Stunde
(`JJJJ-MM-TT HH:00:00`), `visitors` die in dieser Stunde erfassten
Endgeräte. Eine Datei pro Kalendermonat.

### datenqualitaet.md — Vollständigkeitsbericht

Automatisch erzeugte Übersicht: vorhandene vs. erwartete Stunden je Monat,
systemweit fehlende Stunden sowie die Abdeckungszeiträume aller
Erfassungsbereiche.

## Bekannte Einschränkungen und Besonderheiten

1. **Wöchentliche Lücke:** In der Nacht von Freitag auf Samstag fehlt
   regelmäßig die Stunde 23:00 (systemseitiges Wartungsfenster des
   Anbieters).
2. **Ausfälle:** Vereinzelt fehlen Stunden durch System- oder
   Sensorausfälle, u. a. am 06.09.2024 (frühe Morgenstunden) und am
   23./24.05.2025 (ca. 34 Stunden). Details in `datenqualitaet.md`. Die
   typische Abdeckung liegt bei über 98 %. Fehlende Stunden sind in den
   Dateien nicht enthalten (keine Zeilen mit leerem Wert); Stunden mit dem
   Wert 0 sind dagegen echte Messwerte.
3. **Veränderungen der Bereichszuschnitte:** Erfassungsbereiche wurden im
   Betrieb vereinzelt ergänzt, entfernt oder umbenannt (z. B. neue Bereiche
   in der Bahnhofstraße ab Dezember 2025). `stationen.csv` und das GeoJSON
   beschreiben die aktuelle Konfiguration; in den Messwertdateien können
   daher historische Bereichsnamen vorkommen, die dort nicht aufgeführt
   sind. Die Abdeckungszeiträume je Bereich stehen in `datenqualitaet.md`.
4. **September 2024:** In diesem Monat lieferte übergangsweise ein zweiter,
   parallel konfigurierter Satz von Erfassungsbereichen mit generischen
   Namen (z. B. „Niederwall 1") Daten. Diese Werte sind enthalten, um den
   Datenbestand vollständig wiederzugeben, überschneiden sich aber räumlich
   mit den regulären Bereichen — für Auswertungen sollte je Ort nur eine
   Bereichsdefinition verwendet werden.
5. **Vergleichbarkeit:** Die Erfassungsbereiche sind unterschiedlich groß
   (siehe `flaeche_qm`); absolute Werte verschiedener Bereiche sind daher
   nur eingeschränkt vergleichbar.
6. **Datenschutz:** Alle Werte sind aggregierte Zählwerte ohne Geräte- oder
   Personenbezug. Rohdaten einzelner Geräte sind nicht Teil dieses
   Datensatzes.

## Herkunft und Aktualisierung

Die Daten werden über die API des Anbieters (api.ariadne.inc) abgerufen und
täglich um den jeweils abgeschlossenen Vortag ergänzt. Statistische
Auswertungen (z. B. nach Wochentag, Wetter oder Jahreszeit) sind nicht Teil
dieses Datensatzes.

Kontakt für Rückfragen: Stadt Bielefeld / WEGE mbH (Citymanagement).
