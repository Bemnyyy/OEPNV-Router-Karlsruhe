import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from config import config

class GTFSLoader:
    def __init__(self):
        #Speichert alle GTFS-Tabellen als Pandas DataFrame
        self.stops = None #Alle Haltestellen mit Koordinaten und Namen
        self.parent_to_children = None #Mapping
        self.routes = None #Alle Lininen (Bus, Bahn, etc.) mit Typ und Namen
        self.trips = None #Einzelne Fahrten einer Linie zu bestimmten Zeiten
        self.stop_times = None #Ankunfts und Abfahrtszeiten für jede Haltestelle pro Trip
        self.calendar = None #Wochentage, an denen Services aktiv sind
        self.calendar_dates = None #Ausnahmen wie Feiertage, Sonderfahrpläne, etc

    def load_gtfs_data(self) -> bool:
        #Lädt alle GTFS-Dateien aus dem GTFS-Ordner in das Pandas DataFrame
        # Jede GTFS-Datei wird zu einer Tabelle, mit der gearbeitet wird
        #Nach dem Laden wird dann das parent/child Mapping erstellt
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

            self.build_parent_to_child_mapping()    

            calendar_dates_path = os.path.join(config.GTFS_PATH, 'calendar_dates.txt')
            if os.path.exists(calendar_dates_path):
                self.calendar_dates = pd.read_csv(calendar_dates_path)
                print(f"calendar_dates.txt geladen: {len(self.calendar_dates)} Einträge")

            return True
        
        except Exception as e:
            print(f"Fehler beim Laden der GTFS-Daten: {e}")
            return False

    def build_parent_to_child_mapping(self):
        #PROBLEM: Große Bahnhöfe haben mehrere "child stops" (Gleise, Bahnsteige)
        #z.B.: "Hauptbahnhof" hat mehrere Gleise
        #Die Fahrpläne verwenden die spezifische Gleis-ID aber User suchen nach z.B. "Hauptbahnhof"
        
        if self.stops is None:
            print("Warnung: stops ist None - Mapping wird nicht erstellt!")
            return
        self.parent_to_children = {}
        for _, row in self.stops.iterrows():
            parent = row.get('parent_station')
            stop_id = row['stop_id']
            if pd.isna(parent) or not parent:
                #Haltestellen ohne parent_station ist sozusagen ihr eigenener parent
                parent = stop_id
            self.parent_to_children.setdefault(parent, []).append(stop_id)

    def get_all_child_stop_ids(self, stop_id: str) -> list[str]:
        # liefert: {stop_id selbst} ∪ direkte Kinder ∪ Geschwister
        if self.parent_to_children is None:
            return [stop_id]

        if stop_id in self.parent_to_children:          # stop ist Parent
            base = [stop_id] + self.parent_to_children[stop_id]
        else:                                           # stop ist Child
            base = [stop_id]
            for parent, children in self.parent_to_children.items():
                if stop_id in children:
                    base += children + [parent]
                    break
        return list(dict.fromkeys(base))                # Duplikate entfernen
    

    
    def get_stops_by_name(self, name: str) -> List[Dict]:
        #Findet Haltestellen basierend auf Namen       
        if self.stops is None:
            return []
        #Fuzzy-Suche nach Haltestellennamen, Erst exakte Übereinstimmung, dann eine "enthält" Suche
        name_lower = name.lower()
 
        #1.Versuch: Exkater Name:
        matches = self.stops[self.stops['stop_name'].str.lower() == name_lower]
        if matches.empty:
            #fallback: enthält
            #2.Versuch: Name ist enthalten(z.B. "Marktplatz" findet "KA Marktplatz")
            matches = self.stops[self.stops['stop_name'].str.lower().str.contains(name_lower, na=False, regex=False)]
        #regex=False -> pandas behandelt den Suchstring als normalen Text (Einstellung wegen Fehlermeldung)
        #regex=True wurde bedeuten, dass pandas den Suchstring als regulären Ausdruck interpretiert

        return matches.to_dict('records') #Gibt Liste von Dictionaries zurück
    
    def get_route_info(self, route_id: str) -> Optional[Dict]:
        #Holt Informationen zu einer Route
        if self.routes is None:
            return None
        
        route = self.routes[self.routes['route_id'] == route_id]
        if route.empty:
            return None
        
        return route.iloc[0].to_dict()
    
    def get_stop_name(self, stop_id: str) -> str:
        #Holt den Namen einer Haltestelle anhand ihrer ID
        if self.stops is None:
            return stop_id
        
        stop = self.stops[self.stops['stop_id'] == stop_id]
        if not stop.empty:
            return stop.iloc[0]['stop_name']
        return stop_id