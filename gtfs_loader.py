import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from config import config

class GTFSLoader:
    def __init__(self):
        self.stops = None
        self.routes = None
        self.trips = None
        self.stop_times = None
        self.calendar = None
        self.calendar_dates = None

    def load_gtfs_data(self) -> bool:
        #Lädt alle GTFS-Dateien
        try:
            print("Lade GTFS-Daten...")

            #Erforderliche GTFS-Daten
            required_files = {
                'stops': 'stops.txt',
                'routes': 'routes.txt', 
                'trips': 'trips.txt',
                'stop_times': 'stop_times.txt',
                'calendar': 'calendar.txt'               
            }

            for attr, filename in required_files.items():
                filepath = os.path.join(config.GTFS_PATH, filename)
                if not os.path.exists(filepath):
                    print(f"Fehler: {filename} nicht gefunden in {config.GTFS_PATH}")
                    return False
                
                df = pd.read_csv(filepath)
                setattr(self, attr, df)
                print(f"{filename} geladen: {len(df)} Einträge")

            calendar_dates_path = os.path.join(config.GTFS_PATH, 'calendar_dates.txt')
            if os.path.exists(calendar_dates_path):
                self.calendar_dates = pd.read_csv(calendar_dates_path)
                print(f"calendar_dates.txt geladen: {len(self.calendar_dates)} Einträge")

            return True
        
        except Exception as e:
            print(f"Fehler beim Laden der GTFS-Daten: {e}")
            return False
        
    def get_stops_by_name(self, name: str) -> List[Dict]:
        #Findet Haltestellen basierend auf Namen
        if self.stops is None:
            return []
        
        #Fuzzy-Suche nach Haltestellennamen
        name_lower = name.lower()
        matches = self.stops[self.stops['stop_name'].str.lower().str.contains(name_lower, na=False, regex=False)]
        #regex=False -> pandas behandelt den Suchstring als normalen Text (Einstellung wegen Fehlermeldung)
        #regex=True wurde bedeuten, dass pandas den Suchstring als regulären Ausdruck interpretiert

        return matches.to_dict('records')
    
    def get_route_info(self, route_id: str) -> Optional[Dict]:
        #Holt Informationen zu einer Route
        if self.routes is None:
            return None
        
        route = self.routes[self.routes['route_id'] == route_id]
        if route.empty:
            return None
        
        return route.iloc[0].to_dict()
