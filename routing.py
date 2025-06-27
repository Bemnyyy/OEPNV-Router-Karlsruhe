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

    def find_routes(self, start_input: str, end_input: str, departure_time: timedelta, transport_mode: int = 2, max_routes: int = 1) -> List[Journey]:
        print(f"Starte Routing von {start_input} nach {end_input} um {departure_time}")
        
        start_stops, start_walking = self._resolve_location(start_input)
        end_stops, end_walking = self._resolve_location(end_input)
        filtered_connections = self._filter_connections_by_mode(transport_mode)
        
        if not start_stops or not end_stops:
            return []
        
        # Priorisiere "Kaiserstraße" vor "Pyramide" für Marktplatz
        if "marktplatz" in end_input.lower():
            end_stops.sort(key=lambda stop: 0 if "kaiserstraße" in stop['stop_name'].lower() else 1)
        
        for start_stop in start_stops:
            for end_stop in end_stops:                
                journeys = self._dijkstra_routing(
                    start_stop,
                    end_stop,
                    departure_time,
                    filtered_connections,
                    start_walking,
                    end_walking
                )
                
                if journeys:
                    return journeys[:max_routes] # Nur die beste Route
                #Fall bakc: versuche lockerere Zeitbeding.
                for time_offset in [timedelta(minutes=-15), timedelta(minutes=15), timedelta(minutes=30)]:
                    adjusted_time = departure_time + time_offset
                    if adjusted_time.total_seconds() >= 0: #Keine neg Zeiten
                        journeys = self._dijkstra_routing(
                            start_stop, end_stop, adjusted_time, 
                            filtered_connections, start_walking, end_walking
                        )
                        if journeys:
                            return journeys[:max_routes]
                #if journeys: # wenn kombi erfolgreich war, beende suche
                #    break
            #if journeys: # Wenn Start halte erfolgreich, beende suche
            #    break
                continue
        return []   #Keine Route gefunden


    def _format_time(self, td: timedelta) -> str:
        """Hilfsfunktion für Zeitformatierung"""
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"


    def _resolve_location(self, location_input: str) -> Tuple[List[Dict], Optional[Dict]]:
        #Löst Eingabe zu Haltestellen oder Adressen auf
        if __debug__:
            #DEBUGGING
            print(f"Löse auf: '{location_input}'")
        
        #Versuche zuerst als Haltestelle       
        stops = self.gtfs_loader.get_stops_by_name(location_input)
        print(f"Gefundene Haltestellen für '{location_input}': {[s['stop_name'] for s in stops[:3]]}")
        
        if stops:
            # Sammelt alle relevanten Haltestellen IDs (inkl CHild Stops)
            all_stops = []
            seen = set()
            def _add(s):
                if s['stop_id'] not in seen and len(all_stops) < 5: #Maximal 5 stops
                    seen.add(s['stop_id'])
                    all_stops.append(s)
            for stop in stops[:3]: #Nur erste 3 gef. stops
                _add(stop)
                child_ids = self.gtfs_loader.get_all_child_stop_ids(stop['stop_id'])
                for child_id in child_ids[:3]: # auch hier nur die ersten 3
                    if child_id != stop['stop_id']:
                        child_stop = self.gtfs_loader.stops[self.gtfs_loader.stops['stop_id'] == child_id]
                        if not child_stop.empty:
                            _add(child_stop.iloc[0].to_dict())

            # Filtert nur Stops, die im Verbindungsindex vorkommen
            valid_stops = [s for s in all_stops if s['stop_id'] in self.gtfs_processor.connections_by_stop]
            if not valid_stops:
                valid_stops = all_stops[:1]  # Fallback, falls kein gültiger gefunden wurde
            return valid_stops, None


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
            filtered = [conn for conn in self.gtfs_processor.connections 
                if config.GTFS_ROUTE_TYPES.get(conn['route_type'], 'bus') in allowed_types]    
            print(f"Nach Bahn-Filter: {len(filtered)} von {len(self.gtfs_processor.connections)}")
            return filtered
        else: #Bus und Bahn
            return self.gtfs_processor.connections
        
    def _dijkstra_routing(self, start_stop: Dict, end_stop: Dict, departure_time: timedelta,
                        connections: List[Dict], start_walking: Optional[Dict], 
                        end_walking: Optional[Dict]) -> List[Journey]:
        # Konzept -> Dikstra - Algorithmus für öffentliche Verkerhsmittel
        #Statt Entfernung minimieren wird in diesem Algorithmus Zeit + Anzahl Umstiege minimiert
        # Dieser Algorithmus findet die besten Routen zwischen Start und Ziel

        import itertools
        counter = itertools.count() # Eindeutige IDs für Heap-Einträge

        #Verbindungen nach Haltestelle indexieren
        connections_by_stop = {}
    
        for conn in connections:
            stop_id = conn['from_stop_id']
            connections_by_stop.setdefault(stop_id, []).append(conn)                

        max_iterations = 10000 #Iterationen begrenzen, für besser Performance auch auf langsameren Geräten
        # max_iterations wurde auf 10.000 gestellt vorher 5000
        iteration_count = 0

        #Priority Queue: (Ankunftszeit, Transfers, Counter, Haltestelle, Route, Pfad)
        pq = [(departure_time, 0, next(counter), start_stop['stop_id'], None, [])]
        visited = {start_stop['stop_id']: departure_time}  # Speichert beste Ankunftszeit pro Haltestelle
        best_routes = [] #Gefundene komplette Route

        if __debug__:
            print(f"Starte Umstiegs-Suche von {start_stop['stop_id']} nach {end_stop['stop_id']}")
            print(f"Verfügbar ab {start_stop['stop_id']}: {len(connections_by_stop.get(start_stop['stop_id'], []))} Verbindungen")

        # Suche bis zu 3 beste Routen unter der Bedingung, dass der itertaions count kleiner als die maximalen iterationen bleiben
        while pq and len(best_routes) < 3 and iteration_count < max_iterations:
            iteration_count += 1 # Iteration zählt hoch bis max_iteration
            
            # Holt Element mit frühester Ankunftszeit und wenigsten Umstiegen
            current_time, transfers, _, current_stop, last_route, path = heapq.heappop(pq)
            
            #Ziel erreicht? -> Route wird sofort gespeichert
            # INFORMATION für mich: Kritischer Fehler hier gefunden:
            # Journey wurde im else-Block nicht im if Block gebaut --> heißt die Journey wurde dann erstellt wenn das Ziel NICHT erreicht wurde
            # Ziel prüfungsblock wurde geändert!
            if current_stop == end_stop['stop_id']:
                print(f" Ziel erreicht nach {transfers} Umstiegen um {current_time}")

                journey = self._build_journey(path, start_walking, end_walking, departure_time, current_time)
                if journey:
                    best_routes.append(journey)
                    print(f"Route {len(best_routes)} gespeichert")
                continue

            #Prüfe ob bereits bessere Zeit für diese Haltestelle existiert
            if current_stop in visited and visited[current_stop] <= current_time:
                continue #Überspringe, weil schon eine bessere Route gefunden wurde
            visited[current_stop] = current_time
            
            #Zu viele Umstiege vermeiden
            if transfers >= 3:
                continue #Überspringe Routen mit mehr als 3 Umstiegen (Änderbar)
            
            #Verbindungen von aktueller Haltestelle
            if current_stop in connections_by_stop:
                valid_connections = []
                for connection in connections_by_stop[current_stop]:
                    #Nur Verbindungen nach aktueller Zeit
                    if connection['route_id'] == 'WALK':
                        # Fußwege: arrival_time ist die Gehzeit, departure_time wird auf current_time gesetzt
                        connection = dict(connection)  # Kopie erstellen
                        walking_time = connection['arrival_time']  # Gehzeit in timedelta
                        connection['departure_time'] = current_time
                        connection['arrival_time'] = current_time + walking_time
                    elif connection['departure_time'] < current_time:
                        continue
                    
                    #Umstiegszeit prüfen
                    if last_route and last_route != connection['route_id']:                      
                        # Umstieg -> 2 Minuten Puffer
                        wait_time = connection['departure_time'] - current_time
                        if wait_time < timedelta(seconds=config.TRANSFER_TIME_SECONDS):  # aus config (variable)
                            continue
                        new_transfers = transfers + 1 # Umstiege zählen
                    else:
                        new_transfers = transfers

                    valid_connections.append((connection, new_transfers))
                if __debug__ and iteration_count % 1000 == 0:
                    #DEBUGGING: für verfügbare Verbindungen
                    print(f"Iteration {iteration_count}: {current_stop}")
                
                for connection, new_transfers in valid_connections:
                    new_time = connection['arrival_time']
                    dep_time = connection['departure_time']

                    '''#Zeitvalidierung
                    if transfers == 0:
                        # Erstes Segment: Abfahrt nach gewünschter Startzeit
                        if dep_time < departure_time:
                            continue
                    else:
                        # Umstieg: Abfahrt nach Ankunft am Umsteigepunkt + Mindestumstiegszeit
                        if dep_time < current_time + timedelta(seconds=config.TRANSFER_TIME_SECONDS):
                            continue'''

                    if connection['route_id'] == 'WALK':
                        #Fußwege -> nur prüfen dass ankunft nach abfahrt liegt
                        if new_time <= current_time:
                            continue
                    else:
                        # Segment muss in sich valide sein
                        if new_time <= dep_time:
                            continue

                    # Neue Route zum Heap hinzufügen
                    new_path = path + [connection]

                    # Nur hinzufügen wenn Ziel noch nicht erreicht oder bessere Route
                    if (connection['to_stop_id'] not in visited or
                        visited.get(connection['to_stop_id'], timedelta.max) > new_time):

                        # Prioritätsberechnung
                        total_travel_time = new_time - departure_time
                        if total_travel_time.total_seconds() <= 0:
                            continue    #Zeitreisen verhindern

                        priority = total_travel_time + timedelta(minutes=new_transfers * 1)

                        heapq.heappush(pq, (
                            priority, new_transfers, next(counter),
                            connection['to_stop_id'], connection['route_id'], new_path
                        ))
                    #if __debug__:
                    #    print(f"Iteration {iteration_count}, PQ-Länge: {len(pq)}")

            print(f"Suche beendet nach {iteration_count} Iterationen")
            print(f"Gefundene Routen: {len(best_routes)}")
            return best_routes

    def _build_journey(self, connections: List[Dict], start_walking: Optional[Dict], 
                        end_walking: Optional[Dict], departure_time: timedelta, 
                        arrival_time: timedelta) -> Optional[Journey]:
            '''Verwandelt eine Liste von Verbindungen in ein benutzerfreundliches Journey-Objekt'''
            
            if not connections and not start_walking and not end_walking:
                return None
            
            if not connections:
                segments = []
                if start_walking or end_walking:
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

            segments = []
            total_walking_distance = 0.0

            # Start-Fußweg hinzufügen
            if start_walking:
                first_stop = self._get_stop_info(connections[0]['from_stop_id'])
                walking_directions = self.address_processor.generate_walking_directions(
                    start_walking['coordinates'][0], start_walking['coordinates'][1],
                    float(first_stop['stop_lat']), float(first_stop['stop_lon'])
                )
                walking_distance = self.address_processor._haversine_distance(
                    start_walking['coordinates'][0], start_walking['coordinates'][1],
                    float(first_stop['stop_lat']), float(first_stop['stop_lon'])
                )
                segments.append(RouteSegment(
                    mode='walking',
                    to_stop=first_stop['stop_id'],
                    to_stop_name=first_stop['stop_name'],
                    walking_directions=walking_directions,
                    walking_distance=walking_distance
                ))
                total_walking_distance += walking_distance

            # ÖPNV-Segmente: Kombiniere aufeinanderfolgende Verbindungen derselben Linie
            if connections:
                connections_sorted = sorted(connections, key=lambda c: c['departure_time'])
                current_route = None
                route_connections = []
                
                for i, connection in enumerate(connections_sorted):
                    if (connection['route_id'] != current_route or i == len(connections_sorted) - 1):
                        if current_route is not None and route_connections:
                            # Vorherige Route abschließen
                            first_conn = route_connections[0]
                            last_conn = route_connections[-1]
                            from_stop = self._get_stop_info(first_conn['from_stop_id'])
                            to_stop = self._get_stop_info(last_conn['to_stop_id'])
                            
                            segments.append(RouteSegment(
                                mode='transit',
                                from_stop=from_stop['stop_id'],
                                to_stop=to_stop['stop_id'],
                                from_stop_name=from_stop['stop_name'],
                                to_stop_name=to_stop['stop_name'],
                                departure_time=first_conn['departure_time'],
                                arrival_time=last_conn['arrival_time'],
                                route_name=first_conn['route_short_name'] or first_conn['route_long_name'],
                                route_direction=first_conn['headsign'],
                                priority=first_conn['priority']
                            ))
                        
                        # Neue Route starten
                        current_route = connection['route_id']
                        route_connections = [connection]
                    else:
                        # Füge Verbindung zur aktuellen Route hinzu
                        route_connections.append(connection)

            # End-Fußweg hinzufügen
            if end_walking:
                last_stop = self._get_stop_info(connections[-1]['to_stop_id'])
                walking_directions = self.address_processor.generate_walking_directions(
                    float(last_stop['stop_lat']), float(last_stop['stop_lon']),
                    end_walking['coordinates'][0], end_walking['coordinates'][1]
                )
                walking_distance = self.address_processor._haversine_distance(
                    float(last_stop['stop_lat']), float(last_stop['stop_lon']),
                    end_walking['coordinates'][0], end_walking['coordinates'][1]
                )
                segments.append(RouteSegment(
                    mode='walking',
                    from_stop=last_stop['stop_id'],
                    from_stop_name=last_stop['stop_name'],
                    walking_directions=walking_directions,
                    walking_distance=walking_distance
                ))
                total_walking_distance += walking_distance

            # Berechne Statistiken
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
        """Holt Stop-Informationen aus dem GTFS-Loader"""
        stop_data = self.gtfs_loader.stops[self.gtfs_loader.stops['stop_id'] == stop_id]
        if not stop_data.empty:
            return stop_data.iloc[0].to_dict()
        return {
            'stop_id': stop_id,
            'stop_name': self.gtfs_loader.get_stop_name(stop_id),
            'stop_lat': 0.0,
            'stop_lon': 0.0
        }
