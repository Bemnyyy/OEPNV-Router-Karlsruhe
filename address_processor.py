import pandas as pd
import math
from typing import List, Dict, Optional, Tuple
from config import config

class AddressProcessor:
    def __init__(self):
        self.addresses_df = None
        self.load_addresses()

    def load_addresses(self) -> bool:
        #Lädt die Adressendatenbank
        try:
            self.addresses_df = pd.read_csv(config.ADDRESSES_CSV_PATH)
            print(f"{len(self.addresses_df)} Adressen geladen")
            return True
        except Exception as e:
            print(f"Fehler beim Laden der Adressen: {e}")
            return False
        
    def find_address(self, query: str) -> List[Dict]:
        #Sucht Adressen basierend auf Eingaben
        if self.addresses_df is None:
            return []
        
        query_lower = query.lower()
        matches = self.addresses_df[self.addresses_df['full_address'].str.lower().str.contains(query_lower, na=False)]

        return matches.to_dict('records')
    
    def get_nearest_stops(self, lat: float, lon: float, gtfs_loader, max_distance: int = None) -> List[Dict]:
        #Findet nächstgelegene Haltestelle zu Koordinate
        if max_distance is None:
            max_distance = config.MAX_WALKING_DISTANCE_M

        if gtfs_loader.stops is None:
            return []
        
        stops_with_distance = []

        for _, stop in gtfs_loader.stops.iterrows():
            if pd.isna(stop.get('stop_lat')) or pd.isna(stop.get('stop_lon')):
                continue

            distance = self._haversine_distance(
                lat, lon,
                float(stop['stop_lat']),
                float(stop['stop_lon'])
            )

            if distance <= max_distance:
                stop_dict = stop.to_dict()
                stop_dict['walking_distance'] = distance
                stop_dict['walking_time'] = distance / config.WALKING_SPEED_MS
                stops_with_distance.append(stop_dict)
        
        #Sortiere nach Entfernung
        stops_with_distance.sort(key=lambda x: x['walking_distance'])

        return stops_with_distance
    
    def _haversine_distance(self, lat1:float, lon1:float, lat2:float, lon2:float) -> float:
        #Berechnet Luftlinienentfernung zwischen zwei Koordinaten
        R = 6371000 #Erdradius in Metern
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def generate_walking_directions(self, from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> List[str]:
        #Generiert einfache Fußweganweisungen
        #Vereinfachte Richtungsberechnung
        delta_lat = to_lat - from_lat
        delta_lon = to_lon - from_lon

        distance = self._haversine_distance(from_lat, from_lon, to_lat, to_lon)

        #Berechnung Himmelsrichtung
        angle = math.atan2(delta_lon, delta_lat)
        angle_degrees = math.degrees(angle)

        if angle_degrees < 0:
            angle_degrees += 360

        #Bestimme Richtung
        if 337.5 <= angle_degrees or angle_degrees < 22.5:
            direction = "Norden"
        elif 22.5 <= angle_degrees < 67.5:
            direction = "Nordosten"
        elif 67.5 <= angle_degrees < 112.5:
            direction = "Osten"
        elif 112.5 <= angle_degrees < 157.5:
            direction = "Südosten"
        elif 157.5 <= angle_degrees < 202.5:
            direction = "Süden"
        elif 202.5 <= angle_degrees < 247.5:
            direction = "Südwesten"
        elif 247.5 <= angle_degrees < 292.5:
            direction = "Westen"
        else:
            direction = "Nordwesten"

        walking_time = int(distance / config.WALKING_SPEED_MS / 60) #in Minuten

        return [
            f"Gehen Sie {distance:.0f}m in Richtung {direction}",
            f"Gehzeit: ca. {walking_time} Minuten"
        ]
