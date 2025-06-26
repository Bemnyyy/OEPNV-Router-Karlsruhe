# OEPNV-Router-Karlsruhe für den Raum Karlsruhe
Ein intelligenter öffentlicher Nahverkehrs-Router für die Stadt Karlsruhe und Umgebung, der optimale Routen mit minimaler Reisezeit und wenigen Umstiegen findet.

## Features:
- Multimodale Routenplanung: Kombination aus Fußwegen und öffentlichen Verkehrsmitteln
- Intelligente Haltestellensuche: Fuzzy-Suche für Haltestellen und Adressen
- Optimierung Dijkstra-Algorithmus: Speziell für ÖPNV angepasst (Zeit + Umstiege minimieren)
- Echtzeitfähig: Basierend auf aktuellen GTFS - Fahrplandaten des KVV
- Benutzerfreundlich: Einfache Kommandozeile-Oberfläche (Dies soll noch geändert werden zu einer Visualisierung)

## Vorausetzungen
- Python 3.8 oder höher
- Internet - Verbindung für den Download der GTFS-Daten

### Installation ###
## 1. Repository klonen

## 2. Abhängigkeiten installieren
- Installieren Sie zwei nicht-Standard Bibliotheken: pip install pandas, tqdm

## 3. Daten heruntergeladen
#### Erforderliche Daten aus dem Repository herunterladen:
- "ka_bbbike.osm.pbf"
- "karlsruhe_addresses.csv"

#### GTFS - Datensatz (extern):
Der aktuelle KVV - Fahrplan muss seperat heruntergeladen werden:
- Quelle: https://www.kvv.de/fahrplan/fahrplaene/open-data.html
- Format: GTFS (General Transit Feed Specification)
- Entpacken: Alle ".txt" - Dateien in den "gtfs/" - Ordner

## 4. Konfiguration anpassen
Passen Sie die Dateipfade in "config.py" an Ihre lokale Ordnersturktur an:
GTFS_PATH = "pfad/zu/ihren/gtfs/dateien"
ADDRESSES_PATH = "pfad/zu/karlsruhe_addresses.csv"
OSM_PATH = "pfad/zu/ka_bbbike.osm.pbf

## VERWENDUNG ##
### Programm starten -> main.py ausführen (python main.py)

### Beispiel - Sitzung:
=== Karlsruhe ÖPNV-Router ===
Modusauswahl:
1 - Nur Bahn (S-Bahn, Straßenbahn)
2 - Bus und Bahn
Geben Sie 1, 2 oder 0 ein: 2

Start (Adresse oder Haltestelle): Marktplatz
Ziel (Adresse oder Haltestelle): Hauptbahnhof
Bitte Startzeit angeben (HH:MM): 14:30

--- Route 1 ---
Gesamtdauer: 8min
Umstiege: 0
S1 Richtung Hochstetten
Marktplatz → Hauptbahnhof
Abfahrt: 14:32, Ankunft: 14:40

## Projektstruktur
karlsruhe-oepnv-router/
├── main.py # Hauptprogramm
├── gtfs_loader.py # GTFS-Daten laden und verwalten
├── gtfs_processing.py # Verbindungsgraph erstellen
├── routing.py # Dijkstra-Routing-Algorithmus
├── address_resolver.py # Adressauflösung und Fußwege
├── config.py # Konfiguration und Einstellungen
├── extract_addresses.py # OSM-Adressextraktion (optional)
├── data/
│ ├── gtfs/ # KVV GTFS-Daten (herunterladen)
│ ├── ka_bbbike.osm.pbf # OpenStreetMap-Daten aus der Website bbbike
│ └── karlsruhe_addresses.csv
└── README.md

## Algorithmus
Der Router verwendet einen modifizieten Dijkstra - Algorithmus, der speziell für den öffentlichen Nahverkehr optimiert ist:
- Zielfunktion: Minimierung von "Reisezeit + Umstiegspenalty"
- Umstiegslogik: Berücksichtigung von Mindestumstiegszeiten
- Multimodalität: Integration vo Fußwegen zu/von Haltestellen
- Effizienz: Priority - Queue mit Heap für optimale Performance

  ### Optional: Eigene Adressextraktion
  Falls Sie die Adressdaten selbst aus OpenStreetMap extrahieren möchten:

  Neue Conda-Umgebung erstellen:
  condra create -n gtfs_env python = 3.8
  conda activate gtfs_env

  Zusätzliche Abhängigkeiten installieren:
  pip install pyrosm osmnx

  Adressen extrahieren
  python extract_addresses.py
  
  ! Beachten Sie hierbei, dass dies je nach Datengröße der .osm.pbf Datei zu erheblichen Ressourcenverbrauch ihres PCs kommen kann, da dies ein sehr Speicher aufwändiger Prozess       ist!

  Benutzen Sie deshalb, solang Sie diesen Code für Karlsruhe verwenden wollen die im Repository gegebene karlsruhe_addresses.csv.

  ## Bekannte Limitationen
  - Aktuell nur für den KVV-Bereich (Karlsruhe und Umgebung)
  - Keine Echtzeitdaten (nur Fahrplandaten)
  - Fußwege basieren auf Luftlinie-Entfernung
  - Maximale Gehzeit zu Haltestellen: 2000m (kann in "config.py" nach belieben verändert werden)
 
## Beitragen
Dieses Projekt wurde als Abschlussprojekt entwickelt.
Verbesserungsvorschläge ud Bug-Reports sind willkommen!

## Kontakt
Bei Fragen oder Problemen öffnen Sie bitte ein Issue im GitHub Repository.
