import os
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class Config:
    #Pfade zu den Datenquellen - hier Pfade bitte ändern falls diese sich ändern
    GTFS_PATH: str = "google_transit" # Pfad zu den Kvv GTFS Daten
    OSM_PBF_PATH: str = "ka_bbbike.osm.pbf" #Pfad zu der OSM-Datei
    ADDRESSES_CSV_PATH: str = "karlsruhe_addresses.csv" #Pfad zu der Adress-CSV

    #Routing-Einstellungen
    MAX_WALKING_DISTANCE_M: int = 500 #Maximale Fußwegdistanz in Metern
    WALKING_SPEED_MS: float = 1.5 #Gehgeschwindigkeit in m/s
    TRANSFER_TIME_SECONDS: int = 60 #Mindest-Umstiegzeit in Sekunden

    #Verkehrsmittel-Prioritäten
    TRANSPORT_PRIORITIES: Dict[str, int] = field(default_factory=lambda: 
{
        'rail': 1, #Höchste Priorität für Bahnen
        'subway': 1,
        'tram': 2,
        'bus': 3 #Niedrigste Prorität für Busse
    })

    #GTFS Route-Typen Mapping
    GTFS_ROUTE_TYPES: Dict[int, str] = field(default_factory=lambda: {
        0: 'tram',      # Straßenbahn
        1: 'subway',    # U-Bahn
        2: 'rail',      # Bahn
        3: 'bus',       # Bus
        100: 'rail',    # S-Bahn
        109: 'rail',    # Suburban railway
        400: 'subway',  # Urban railway
        700: 'bus',     # Bus service
        900: 'tram',    # Tram service
        1000: 'rail',
        1100: 'tram',
        1200: 'bus'
    })

#Globale Konfigurationsinstanz
config = Config()