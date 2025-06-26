# gtfs_processing.py
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from gtfs_loader import GTFSLoader
from config import config
from tqdm import tqdm

class GTFSProcessor:
    def __init__(self, gtfs_loader: GTFSLoader):
        self.gtfs = gtfs_loader
        self.connections = []

    def build_connection_graph(self, target_date: datetime) -> bool:
        """Erstellt Verbindungsgraph für einen bestimmten Tag"""
        try:
            print("Erstelle Verbindungsgraph...")

            # Filtere aktive Services für das Zieldatum
            active_services = self._get_active_services(target_date)
            if not active_services:
                print("Keine aktiven Services für das Datum gefunden")
                return False

            # Filtere Trips nach aktiven Services
            active_trips = self.gtfs.trips[self.gtfs.trips['service_id'].isin(active_services)]

            print(f"Aktive Trips: {len(active_trips)}")

            # Gruppiert Stop Times einmalig nach trip_id
            stop_times_grouped = self.gtfs.stop_times.groupby('trip_id')

            self.connections = []

            # tqdm-Fortschrittsbalken für Fortschrittsbalken
            for _, trip in tqdm(active_trips.iterrows(), total=len(active_trips), desc='Verarbeite Trips'):
                try:
                    trip_stops = stop_times_grouped.get_group(trip['trip_id']).sort_values('stop_sequence')
                except KeyError:
                    continue  # Falls ein Trip keine Stop Times hat

                if len(trip_stops) < 2:
                    continue

                route_info = self.gtfs.get_route_info(trip['route_id'])
                if not route_info:
                    continue

                # Erstelle Verbindungen zwischen aufeinanderfolgenden Haltestellen
                for i in range(len(trip_stops) - 1):
                    from_stop = trip_stops.iloc[i]
                    to_stop = trip_stops.iloc[i + 1]

                    connection = {
                        'trip_id': trip['trip_id'],
                        'route_id': trip['route_id'],
                        'route_short_name': route_info.get('route_short_name', ''),
                        'route_long_name': route_info.get('route_long_name', ''),
                        'route_type': route_info.get('route_type', 3),
                        'from_stop_id': from_stop['stop_id'],
                        'to_stop_id': to_stop['stop_id'],
                        'departure_time': self._parse_gtfs_time(from_stop['departure_time']),
                        'arrival_time': self._parse_gtfs_time(to_stop['arrival_time']),
                        'headsign': trip.get('trip_headsign', ''),
                        'priority': config.TRANSPORT_PRIORITIES.get(
                            config.GTFS_ROUTE_TYPES.get(route_info.get('route_type', 3), 'bus'), 3
                        )
                    }
                    self.connections.append(connection)

            print(f"\n{len(self.connections)} Verbindungen erstellt")
            
            self.connections_by_stop = {}
            for conn in self.connections:
                stop_id = conn['from_stop_id']
                if stop_id not in self.connections_by_stop:
                    self.connections_by_stop[stop_id] = []
                self.connections_by_stop[stop_id].append(conn)
            
            print(f"Verbindungsindex für {len(self.connections_by_stop)} Haltestellen erstellt")

            return True

        except Exception as e:
            print(f"Fehler beim Erstellen des Verbindungsgraphs: {e}")
            return False

    def _get_active_services(self, target_date: datetime) -> List[str]:
        """Ermittelt aktive Services für ein Datum"""
        active_services = []

        if self.gtfs.calendar is not None:
            weekday = target_date.strftime('%A').lower()
            date_str = target_date.strftime('%Y%m%d')

            for _, service in self.gtfs.calendar.iterrows():
                # Prüfe ob Service an diesem Wochentag aktiv ist
                if service.get(weekday, 0) == 1:
                    # Prüfe Gültigkeitszeitraum
                    start_date = str(service['start_date'])
                    end_date = str(service['end_date'])

                    if start_date <= date_str <= end_date:
                        active_services.append(service['service_id'])

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

    def _parse_gtfs_time(self, time_str: str) -> timedelta:
        """Konvertiert GTFS-Zeitformat zu timedelta"""
        try:
            parts = time_str.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2]) if len(parts) > 2 else 0

            return timedelta(hours=hours, minutes=minutes, seconds=seconds)
        except:
            return timedelta(0)
