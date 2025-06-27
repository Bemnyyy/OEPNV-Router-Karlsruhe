import pandas as pd
import itertools
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from gtfs_loader import GTFSLoader
from config import config
from tqdm import tqdm
from address_processor import AddressProcessor

class GTFSProcessor:
    def __init__(self, gtfs_loader: GTFSLoader):
        self.gtfs = gtfs_loader
        self.connections = [] #Liste aller möglichen Verbindungen
        self.connections_by_stop = {} # Index: stop_id -> Liste von Verbindungen
        
        
    def build_connection_graph(self, target_date: datetime) -> bool:
        """Erstellt Verbindungsgraph für einen bestimmten Tag"""
        address_processor = AddressProcessor()

        try:
            print("Erstelle Verbindungsgraph...")

            # Filtere aktive Services für das Zieldatum
            #1.: Welche Service sind aktiv?
            active_services = self._get_active_services(target_date)
            #Prüft calendar.txt -> Fährt die Linie montags? dienstags? mittwochs? ...
            #Prüft caledar_dates.txt -> Welche Ausnahmen gibt es?

            #Sicherung, wenn keine aktiven Services gefunden wurden
            if not active_services:
                print("Keine aktiven Services für das Datum gefunden")
                return False

            # Filtere Trips nach aktiven Services
            #2.: Welche Trips fahren heute?
            # Trip = eine konkrete Fahrt einer Linie zu einer bestimmten Zeit
            active_trips = self.gtfs.trips[self.gtfs.trips['service_id'].isin(active_services)]
            print(f"Aktive Trips: {len(active_trips)}") #Zeigt alle aktiven Trips

            #DEBUGGING
            route_ids = set(active_trips['route_id'].unique())
            print(f"Aktive Route-IDs: {len(route_ids)}")
            if len(route_ids) < 50: #Falls zu wenige Routen
                print("ACHTUNG: Sehr wenige aktive Routen gefunden")
                print("Versuche alle verfügbaren Services...")
                active_trips = self.gtfs.trips #Alle trips verwenden
                print(f"Alle verfügbaren trips: {len(active_trips)}")

            # Gruppiere Stop Times einmalig nach trip_id (Performance-Tipp)
            # 3.: Für jeden Trip werden alle Verbindungen zwischen Haltestellen erstellt
            stop_times_grouped = self.gtfs.stop_times.groupby('trip_id') #.groupby - Optimierung für schnellen Zugriff

            # --- VERBINDUNGSGRAPH AUFBAUEN ---
            self.connections = []

            # tqdm-Fortschrittsbalken für Fortschrittsbalken darstellung
            for _, trip in tqdm(active_trips.iterrows(), total=len(active_trips), desc='Verarbeite Trips'):
                try:
                    trip_stops = stop_times_grouped.get_group(trip['trip_id']).sort_values('stop_sequence') #Holt alle Haltestellen dieses Trips in der richtigen Reihenfolge
                except KeyError:
                    continue  # Falls ein Trip keine Stop Times hat

                if len(trip_stops) < 2:
                    continue

                route_info = self.gtfs.get_route_info(trip['route_id']) or {'route_short_name': 'N/A', 'route_type': 3}
                #if not route_info:
                #    continue               Wurde hier entfernt weil oben auf Standardwerte gesetzt wurde

                # Erstelle Verbindungen zwischen aufeinanderfolgenden Haltestellen
                # Verwendet Vektoroperationen mit pandas statt doppelte Schleifen weil dies bei großen Netzen langsam sein kann
                for i in range(1, len(trip_stops)):
                    from_stop = trip_stops.iloc[i-1]
                    to_stop = trip_stops.iloc[i]

                    # Erstelle Verbindungsobjekt mit allen wichtigen Informationen
                    dep_time = self._parse_gtfs_time(from_stop['departure_time'])
                    arr_time = self._parse_gtfs_time(to_stop['arrival_time'])

                    if arr_time < dep_time:
                        arr_time += timedelta(days=1)

                    travel = arr_time - dep_time
                    if travel <= timedelta(0) or travel > timedelta(hours=3):
                        continue


                    connection = {
                        'trip_id': trip['trip_id'],
                        'route_id': trip['route_id'],
                        'route_short_name': route_info.get('route_short_name', ''),
                        'route_long_name': route_info.get('route_long_name', ''),
                        'route_type': route_info.get('route_type', 3),
                        'from_stop_id': from_stop['stop_id'],
                        'to_stop_id': to_stop['stop_id'],
                        'departure_time': dep_time,
                        'arrival_time': arr_time,
                        'headsign': trip.get('trip_headsign', ''),
                        'priority': config.TRANSPORT_PRIORITIES.get(
                            config.GTFS_ROUTE_TYPES.get(route_info.get('route_type', 3), 'bus'), 3
                        )
                    }

                    self.connections.append(connection)

            print(f"\n{len(self.connections)} Verbindungen erstellt") 
                             
            # 4.: Index erstellen für schnellen Zugriff
            # Anstatt, dass alle Verbindungen durchsucht werden -> direkte filterung nach Start und Ziel Haltestelle
            self.connections_by_stop = {}
            for conn in self.connections:
                stop_id = conn['from_stop_id']
                if stop_id not in self.connections_by_stop:
                    self.connections_by_stop[stop_id] = []
                self.connections_by_stop[stop_id].append(conn)
            
            print(f"Verbindungsindex für {len(self.connections_by_stop)} Haltestellen erstellt")
            

            # 5. Füge Fußwege zwischen nahen Haltestellen hinzu
            max_walk = config.MAX_WALKING_DISTANCE_M
            # Filtere Stops mit gültigen Koordinaten
            valid_stops = self.gtfs.stops[
                (self.gtfs.stops['stop_lat'].notna()) & 
                (self.gtfs.stops['stop_lon'].notna()) &
                (self.gtfs.stops['stop_lat'] != 0) &
                (self.gtfs.stops['stop_lon'] != 0)
            ][['stop_id', 'stop_lat', 'stop_lon']]

            stops = valid_stops.to_dict('records')
            print(f"Gefilterte Stops mit gültigen Koordinaten: {len(stops)}")

            walking_connections_added = 0

            if __debug__:
                print(f"Prüfe {len(stops)} Haltestellen für Fußwege...")
            for i, stop_a in enumerate(stops):
                for j, stop_b in enumerate(stops[i+1:], i+1):
                    try:
                        dist = address_processor._haversine_distance(
                            float(stop_a['stop_lat']), float(stop_a['stop_lon']),
                            float(stop_b['stop_lat']), float(stop_b['stop_lon'])
                        )

                        #Erweitert Fußwege für KA Halten
                        is_karlsruhe_a = stop_a['stop_id'].startswith('de:08212:')
                        is_karlsruhe_b = stop_b['stop_id'].startswith('de:08212:')
                        max_dist = max_walk * 2 if (is_karlsruhe_a and is_karlsruhe_b) else max_walk

                        if dist <= max_dist:
                            # Bidirektionale Fußwege hinzufügen
                            for sa, sb in [(stop_a, stop_b), (stop_b, stop_a)]:
                                walking_time = max(30, round(dist / config.WALKING_SPEED_MS))  # Mindestens 30 Sekunden
                                
                                self.connections_by_stop.setdefault(sa['stop_id'], []).append({
                                    'from_stop_id': sa['stop_id'],
                                    'to_stop_id': sb['stop_id'],
                                    'departure_time': timedelta(0),
                                    'arrival_time': timedelta(seconds=walking_time),
                                    'route_id': 'WALK',
                                    'route_short_name': 'Fußweg',
                                    'route_long_name': f'Fußweg ({dist:.0f}m)',
                                    'route_type': 3,
                                    'headsign': f'zu {sb["stop_id"]}',
                                    'priority': config.TRANSPORT_PRIORITIES.get('bus', 3)
                                })
                                walking_connections_added += 1
                                
                    except (ValueError, TypeError) as e:
                        continue  # Überspringe fehlerhafte Koordinaten
            print(f"Fußwege hinzugefügt: {walking_connections_added} Verbindungen")

            

            print(f"\n=== VERBINDUNGSSTATISTIK ===")
            total_connections = sum(len(conns) for conns in self.connections_by_stop.values())
            walking_connections = sum(1 for conns in self.connections_by_stop.values() 
                                    for conn in conns if conn['route_id'] == 'WALK')
            print(f"Gesamte Verbindungen: {total_connections}")
            print(f"Davon Fußwege: {walking_connections}")
            print(f"ÖPNV-Verbindungen: {total_connections - walking_connections}")

            # Zeige Beispiel-Haltestellen mit Verbindungen
            print("\nBeispiel-Haltestellen mit Verbindungen:")
            for i, (stop_id, conns) in enumerate(self.connections_by_stop.items()):
                if i < 10 and len(conns) > 0:
                    walking = sum(1 for c in conns if c['route_id'] == 'WALK')
                    transit = len(conns) - walking
                    print(f"  {stop_id}: {len(conns)} total ({transit} ÖPNV, {walking} Fußweg)")
            print("=== ENDE STATISTIK ===\n")
            
            #DEBUGGING: Prüft KA Verbindungen speziell
            karlsruhe_connections = [c for c in self.connections if c['from_stop_id'].startswith('de:08212:')]
            print(f"\nKarlsruher Verbindungen (de:08212:): {len(karlsruhe_connections)}")

            if len(karlsruhe_connections) < 1000:
                print("WARNUNG: Sehr wenige Karlsruher Verbindungen gefunden!")
                # Zeige Beispiele
                for i, conn in enumerate(karlsruhe_connections[:5]):
                    print(f"  {conn['from_stop_id']} -> {conn['to_stop_id']} ({conn['route_short_name']})")

            # Zeige Verbindungen für die gesuchten Haltestellen
            test_stops = ['de:08212:1115:1:1', 'de:08212:1111:1:1']  # Neureut Kirchfeld, Bärenweg
            for stop_id in test_stops:
                if stop_id in self.connections_by_stop:
                    conns = self.connections_by_stop[stop_id]
                    print(f"Verbindungen ab {stop_id}: {len(conns)}")
                    for conn in conns[:3]:
                        print(f"  -> {conn['to_stop_id']} ({conn['route_short_name']})")
                else:
                    print(f"KEINE Verbindungen ab {stop_id}!")

            return True
        
        except Exception as e:
            print(f"Fehler beim Erstellen des Verbindungsgraphs: {e}")
            return False

    def _get_active_services(self, target_date: datetime) -> List[str]:
        """Ermittelt aktive Services für ein Datum"""
        active_services = []

        #Sicherung, dass calendar einträge bestehen werden diese weiter gegeben
        if self.gtfs.calendar is not None:
            #weekday = target_date.strftime('%A').lower()
            weekday_en = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            weekday_index = target_date.weekday()
            weekday_col = weekday_en[weekday_index]

            date_str = target_date.strftime('%Y%m%d')

            for _, service in self.gtfs.calendar.iterrows():
                # Prüfe ob Service an diesem Wochentag aktiv ist
                if service.get(weekday_col, 0) == 1:
                    # Prüfe Gültigkeitszeitraum
                    start_date = str(service['start_date'])
                    end_date = str(service['end_date'])

                    if start_date <= date_str <= end_date:
                        active_services.append(service['service_id'])
            if not active_services:
                print("WARNUUUNG: Keine Services für heute gefunden, verwende alle verfügbaren Services")
                active_services = self.gtfs.calendar['service_id'].unique().tolist()
                print(f"Fallback: {len(active_services)} Services geladen")
        
        
        # Prüfe calendar_dates für Ausnahmen
        if self.gtfs.calendar_dates is not None:
            date_str = target_date.strftime('%Y%m%d')
            if 'date' not in self.gtfs.calendar_dates.columns:
                raise ValueError("Spalte 'date' fehlt in calendar_dates")
            exceptions = self.gtfs.calendar_dates[
                self.gtfs.calendar_dates['date'].astype(str) == date_str
            ]

            for _, exception in exceptions.iterrows():
                if exception['exception_type'] == 1:  # Service hinzugefügt
                    if exception['service_id'] not in active_services:
                        active_services.append(exception['service_id'])
                elif exception['exception_type'] == 2:  # Service entfernt
                    if exception['service_id'] in active_services:
                        active_services.remove(exception['service_id'])

        return active_services

    # ersetze _parse_gtfs_time komplett
    def _parse_gtfs_time(self, time_str: str) -> timedelta:
        """GTFS-Zeit (HH:MM[:SS]) → timedelta, inkl. Stunden ≥24"""
        try:
            h, m, s = (time_str.split(':') + ['0', '0'])[:3]
            h, m, s = int(h), int(m), int(s)
            d, h = divmod(h, 24)          # Tage und Reststunden
            return timedelta(days=d, hours=h, minutes=m, seconds=s)
        except Exception:
            return timedelta(0)