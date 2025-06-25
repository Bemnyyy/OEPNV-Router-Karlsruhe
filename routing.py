import heapq
import itertools
from datetime import datetime, timedelta, time
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from gtfs_processing import GTFSProcessor
from gtfs_loader import GTFSLoader
from address_processor import AddressProcessor
from config import config
counter = itertools.count()

@dataclass
class RouteSegment:
    #Repräentiert ein Segment einer Route
    mode: str  # 'walking', 'transit'
    from_stop: Optional[str] = None
    to_stop: Optional[str] = None
    from_stop_name: Optional[str] = None
    to_stop_name: Optional[str] = None
    departure_time: Optional[timedelta] = None
    arrival_time: Optional[timedelta] = None
    route_name: Optional[str] = None
    route_direction: Optional[str] = None
    walking_directions: Optional[List[str]] = None
    walking_distance: Optional[float] = None
    priority: int = 3

@dataclass
class Journey:
    #Komplete Reise mit allen Segmenten
    segments: List[RouteSegment]
    total_duration: timedelta
    total_walking_distance: float
    departure_time: timedelta
    arrival_time: timedelta
    transfers: int

class PublicTransportRouter:
    def __init__(self, gtfs_loader: GTFSLoader, gtfs_processor: GTFSProcessor, address_processor: AddressProcessor):
        self.gtfs_loader = gtfs_loader
        self.gtfs_processor = gtfs_processor
        self.address_processor = address_processor

    def find_routes(self, start_input: str, end_input: str, departure_time: timedelta, transport_mode: int = 2, max_routes: int = 3) -> List[Journey]:
        '''Hauptfunktion für Routensuche
        transport_mode: 1 = nur Bahn, 2 = Bus und Bahn'''
        print(f"Starte Routing von {start_input} nach {end_input} um {departure_time}")

        #Bestimme Start- und Zielpunkte
        start_stops, start_walking = self._resolve_location(start_input)
        end_stops, end_walking = self._resolve_location(end_input)

        #Filtere Verbindungen nach Verkehrsmittel-Modus
        filtered_connections = self._filter_connections_by_mode(transport_mode)

        if not start_stops or not end_stops:
            print("Keine gültigen Haltestellen gefunden")
            return []
        
        #DEBUGGING
        print(f"Gefilterte Verbindungen: {len(filtered_connections)} von {len(self.gtfs_processor.connections)}")

        all_journeys = []

        #Suche Routen zwischen allen Kombinationen von Start- und Zielhaltestellen 
        for start_stop in start_stops[:3]: #Limitiere auf 3 nächste Haltestellen
            for end_stop in end_stops[:3]:
                journeys = self._dijkstra_routing(
                    start_stop, end_stop, departure_time, filtered_connections, start_walking, end_walking
                )
                all_journeys.extend(journeys)

        #Sortiert und filtert beste Routen
        all_journeys.sort(key=lambda j: (j.transfers, j.total_duration, -j.segments[0].priority))

        return all_journeys[:max_routes]
    
    def _resolve_location(self, location_input: str) -> Tuple[List[Dict], Optional[Dict]]:
        #Löst Eingabe zu Haltestellen oder Adressen auf
        #DEBUGGING
        print(f"Löse auf: '{location_input}'")
        
        #Versuche zuerst als Haltestelle       
        stops = self.gtfs_loader.get_stops_by_name(location_input)
        print(f"Gefundene Haltestellen für '{location_input}': {[s['stop_name'] for s in stops[:3]]}")
        print("Alle gefundenen Stops für Eingabe:", [s['stop_id'] for s in stops])

        
        if stops:
            #Filtere nur Haltestellem die im Verbindungsindex existieren
            valid_stops = []
            for stop in stops:
                for stop['stop_id'] in self.gtfs_processor.connections_by_stop:
                    valid_stops.append(stop)
                
            print(f"Gefilterte gültige Haltestellen: {len(valid_stops)} von {len(stops)}")
            
            if not valid_stops:
                print("Warnung: Keine gültige Haltestelle gefunden. Verwende alle gefundenen Stops.")
                valid_stops = stops
            #Nimmt nur die erste gültige Haltestelle
            if valid_stops:
                return [valid_stops[0]], None

        #Versuche als Adresse
        addresses = self.address_processor.find_address(location_input)
        if not addresses:
            return [], None
        
        #Nimmt beste Adresse
        best_address = addresses[0]
        nearby_stops = self.address_processor.get_nearest_stops(best_address['lat'], best_address['lon'], self.gtfs_loader)
        walking_info = {
            'address': best_address,
            'coordinates': (best_address['lat'], best_address['lon'])
        }
        return nearby_stops, walking_info
    
    def _filter_connections_by_mode(self, transport_mode: int) -> List[Dict]:
        #Filtert Verbindungen nach Verkehrsmittel-Modus

        #DEBUGGING: Zeige Route-Typen im System
        route_types = set()
        for conn in self.gtfs_processor.connections:
            route_types.add(conn['route_type'])
        print(f"Gefundene Route-Typen im System: {sorted(route_types)}")

        if transport_mode == 1: #Nur Bahn
            allowed_types = ['rail', 'subway', 'tram']
            filtered = [conn for conn in self.gtfs_processor.connections if config.GTFS_ROUTE_TYPES.get(conn['route_type'], 'bus') in allowed_types]    
            print(f"Nach Bahn-Filter: {len(filtered)} von {len(self.gtfs_processor.connections)}")
            return filtered
        else: #Bus und Bahn
            return self.gtfs_processor.connections
        
    def _dijkstra_routing(self, start_stop: Dict, end_stop: Dict, departure_time: timedelta, connections: List[Dict], start_walking: Optional[Dict], end_walking: Optional[Dict]) -> List[Journey]:
        import itertools
        counter = itertools.count()
        #Priority Queue: (Ankunftszeit, Transfers, Counter, Haltestelle, Route, Pfad)
        pq = [(departure_time, 0, next(counter), start_stop['stop_id'], None, [])]
        visited = {}  # Dict statt Set - speichere beste Zeit pro Haltestelle
        best_routes = []
        
        #Verbindungen nach Haltestelle indexieren
        connections_by_stop = {}
        for conn in connections:
            stop_id = conn['from_stop_id']
            if stop_id not in connections_by_stop:
                connections_by_stop[stop_id] = []
            connections_by_stop[stop_id].append(conn)
        
        #DEBUGGING: Verbindungsindexierung prüfen
        print(f"Verbindungen indexiert für {len(connections_by_stop)} Haltestellen")
        if start_stop['stop_id'] in connections_by_stop:
            print(f"Start-Haltestelle {start_stop['stop_id']} hat {len(connections_by_stop[start_stop['stop_id']])} Verbindungen")
        else:
            print(f"PROBLEM: Start-Haltestelle {start_stop['stop_id']} nicht in Verbindungsindex!")
        
        #Zeige erste 5 Haltestellen im Index
        for i, (stop_id, conns) in enumerate(connections_by_stop.items()):
            if i < 5:
                print(f"  {stop_id}: {len(conns)} Verbindungen")
        
        #DEBUGGING: Prüfe erreichbare Haltestellen von Start (nur einmal!)
        reachable_stops = set()
        if start_stop['stop_id'] in connections_by_stop:
            for conn in connections_by_stop[start_stop['stop_id']]:
                reachable_stops.add(conn['to_stop_id'])
        print(f"Von Start erreichbare Haltestellen: {len(reachable_stops)}")
        
        #DEBUGGING: Prüfe Haltestellen mit Verbindung zum Ziel (nur einmal!)
        incoming_stops = set()
        for conn in connections:
            if conn['to_stop_id'] == end_stop['stop_id']:
                incoming_stops.add(conn['from_stop_id'])
        print(f"Haltestellen mit Verbindung zum Ziel: {len(incoming_stops)}")
        
        max_iterations = 5000
        iteration_count = 0
        
        print(f"Starte Umstiegs-Suche von {start_stop['stop_id']} nach {end_stop['stop_id']}")
        
        while pq and len(best_routes) < 3 and iteration_count < max_iterations:
            iteration_count += 1
            
            current_time, transfers, _, current_stop, last_route, path = heapq.heappop(pq)
            
            #DEBUGGING: nur alle 100 Iterationen (verhindert Spam)
            if iteration_count % 100 == 0:
                print(f"Iteration {iteration_count}: Besuche {current_stop}, Zeit: {current_time}, Transfers: {transfers}")
            
            #Ziel erreicht - SOFORT Route speichern
            if current_stop == end_stop['stop_id']:
                print(f"ZIEL ERREICHT nach {transfers} Umstiegen um {current_time}!")
            else:
                #DEBUGGING: Zeige wie nah wir dem Ziel kommen
                if iteration_count % 100 == 0:
                    print(f"Aktuell bei: {current_stop}, Ziel: {end_stop['stop_id']}")
                journey = self._build_journey(path, start_walking, end_walking, 
                                            departure_time, current_time)
                if journey:
                    best_routes.append(journey)
                    print(f"Route {len(best_routes)} gespeichert")
                continue
            
            #Prüfe ob bereits bessere Zeit für diese Haltestelle existiert
            if current_stop in visited and visited[current_stop] <= current_time:
                continue
            visited[current_stop] = current_time
            
            #Zu viele Umstiege vermeiden
            if transfers >= 3:
                continue
            
            #Verbindungen von aktueller Haltestelle
            if current_stop in connections_by_stop:
                valid_connections = []
                
                for connection in connections_by_stop[current_stop]:
                    #Nur Verbindungen nach aktueller Zeit
                    if connection['departure_time'] <= current_time:
                        continue
                    
                    #Umstiegszeit prüfen
                    new_transfers = transfers
                    if last_route and last_route != connection['route_id']:
                        new_transfers += 1
                        wait_time = connection['departure_time'] - current_time
                        if wait_time < timedelta(seconds=60):  # Mindestens 1 Minute Umstieg
                            continue
                    
                    valid_connections.append((connection, new_transfers))
                
                #DEBUGGING: Zeige verfügbare Verbindungen (nur alle 100 Iterationen)
                if iteration_count % 100 == 0 and valid_connections:
                    print(f"  → {len(valid_connections)} verfügbare Verbindungen")
                
                for connection, new_transfers in valid_connections:
                    new_path = path + [connection]
                    new_time = connection['arrival_time']
                    
                    #Nur hinzufügen wenn Ziel noch nicht erreicht oder bessere Route
                    if (connection['to_stop_id'] not in visited or 
                        visited.get(connection['to_stop_id'], timedelta.max) > new_time):
                        
                        heapq.heappush(pq, (
                            new_time, new_transfers, next(counter), 
                            connection['to_stop_id'], connection['route_id'], new_path
                        ))
        
        print(f"Suche beendet nach {iteration_count} Iterationen")
        print(f"Gefundene Routen: {len(best_routes)}")
        return best_routes



    def _build_journey(self, connections: List[Dict], start_walking: Optional[Dict], end_walking: Optional[Dict], departure_time: timedelta, arrival_time: timedelta) -> Optional[Journey]:
        
        # Spezialfall: Keine Verbindungen (Start = Ziel)
        if not connections:
            segments = []
            if start_walking or end_walking:
                # Füge minimalen Fußweg hinzu
                segments.append(RouteSegment(
                    mode='walking',
                    walking_directions=['Sie sind bereits am Ziel'],
                    walking_distance=0.0
                ))
            
            return Journey(
                segments=segments,
                total_duration=timedelta(0),
                total_walking_distance=0.0,
                departure_time=departure_time,
                arrival_time=departure_time,
                transfers=0
            )       
        
        #Baut Journey-Objekt aus Verbindungsliste
        segments = []
        total_walking_distance = 0.0

        #Start-Fußweg hinzufügen
        if start_walking:
            first_stop = self._get_stop_info(connections[0]['from_stop_id'])
            walking_directions = self.address_processor.generate_walking_directions(start_walking['coordinates'][0], start_walking['coordinates'][1], float(first_stop['stop_lat']), float(first_stop['stop_lon']))
            walking_distance = self.address_processor._haversine_distance(start_walking['coordinates'][0], start_walking['coordinates'][1], float(first_stop['stop_lat']), float(first_stop['stop_lon']))

            segments.append(RouteSegment(
                mode='walking',
                to_stop=first_stop['stop_id'],
                to_stop_name=first_stop['stop_name'],
                walking_directions=walking_directions,
                walking_distance=walking_distance
            ))
            total_walking_distance += walking_distance

        #ÖPNV-Segmente hinzufügen
        current_route = None
        route_start_connection = None

        for i, connection in enumerate(connections):
            #Neue Route oder letzte Verbindung
            if (connection['route_id'] != current_route or i == len(connections) - 1):
                if current_route is not None:
                    #Vorherige Route abschließen
                    from_stop = self._get_stop_info(route_start_connection['from_stop_id'])
                    to_stop = self._get_stop_info(connections[i-1]['to_stop_id'])

                    segments.append(RouteSegment(
                        mode='transit',
                        from_stop=from_stop['stop_id'],
                        to_stop=to_stop['stop_id'],
                        from_stop_name=from_stop['stop_name'],
                        to_stop_name=to_stop['stop_name'],
                        departure_time=route_start_connection['departure_time'],
                        arrival_time=connections[i-1]['arrival_time'],
                        route_name=route_start_connection['route_short_name'] or route_start_connection['route_long_name'],
                        route_direction=route_start_connection['headsign'],
                        priority=route_start_connection['priority']
                    ))

                #Neue Route starten
                current_route = connection['route_id']
                route_start_connection = connection
                
                #Letzte Verbindung behandeln
                if i == len(connections) - 1:
                    from_stop=self._get_stop_info(connection['from_stop_id'])
                    to_stop=self._get_stop_info(connection['to_stop_id'])

                    segments.append(RouteSegment(
                        mode='transit',
                        from_stop=from_stop['stop_id'],
                        to_stop=to_stop['stop_id'],
                        from_stop_name=from_stop['stop_name'],
                        to_stop_name=to_stop['stop_name'],
                        departure_time=connection['departure_time'],
                        arrival_time=connection['arrival_time'],
                        route_name=connection['route_short_name'] or connection['route_long_name'],
                        route_direction=connection['headsign'],
                        priority=connection['priority']
                    ))
        
        #End-Fußweg hinzufügen
        if end_walking:
            last_stop = self._get_stop_info(connections[-1]['to_stop_id'])
            walking_directions = self.address_processor.generate_walking_directions(float(last_stop['stop_lat']), float(last_stop['stop_lon']), end_walking['coordinates'][0], end_walking['coordinates'][1])
            walking_distance = self.address_processor._haversine_distance(float(last_stop['stop_lat']), float(last_stop['stop_lon']), end_walking['coordinates'][0], end_walking['coordinates'][1])
            segments.append(RouteSegment(
                mode='walking',
                from_stop=last_stop['stop_id'],
                from_stop_name=last_stop['stop_name'],
                walking_directions=walking_directions,
                walking_distance=walking_distance
            ))
            total_walking_distance += walking_distance
        
        #Berechne Statistiken
        total_duration = arrival_time - departure_time
        transfers = len([s for s in segments if s.mode == 'transit']) - 1

        return Journey(
            segments=segments,
            total_duration=total_duration,
            total_walking_distance=total_walking_distance,
            departure_time=departure_time,
            arrival_time=arrival_time,
            transfers=max(0, transfers)  
        )
    
    def _get_stop_info(self, stop_id: str) -> Dict:
        #Holt Haltestelleninformationen ein
        stop = self.gtfs_loader.stops[self.gtfs_loader.stops['stop_id'] == stop_id]
        if not stop.empty:
            return stop.iloc[0].to_dict()
        return {'stop_id': stop_id, 'stop_name': stop_id, 'stop_lat': 0, 'stop_lon': 0}
