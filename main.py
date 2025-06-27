# main.py
import sys
from datetime import datetime, timedelta, time
from typing import Optional
from gtfs_loader import GTFSLoader
from gtfs_processing import GTFSProcessor
from address_processor import AddressProcessor
from routing import PublicTransportRouter, Journey, RouteSegment
from config import config

class KarlsruheTransitRouter:
    def __init__(self):
        print("=== Karlsruhe ÖPNV-Router ===")
        print("Initialisiere System...")
        
        # Komponenten initialisieren
        self.gtfs_loader = GTFSLoader()
        self.address_processor = AddressProcessor()
        self.gtfs_processor = None
        self.router = None
        
        # System laden
        if not self._initialize_system():
            print("Fehler bei der Initialisierung. Programm wird beendet.")
            sys.exit(1)
    
    def _initialize_system(self) -> bool:
        """Initialisiert alle Systemkomponenten"""
        # GTFS-Daten laden
        if not self.gtfs_loader.load_gtfs_data():
            return False
        
        # GTFS-Processor initialisieren
        self.gtfs_processor = GTFSProcessor(self.gtfs_loader)
        
        # Verbindungsgraph für heute erstellen
        today = datetime.now()
        if not self.gtfs_processor.build_connection_graph(today):
            return False

        # Router initialisieren
        self.router = PublicTransportRouter(
            self.gtfs_loader, self.gtfs_processor, self.address_processor
        )
        
        print("✓ System erfolgreich initialisiert")
        return True
    
    def run(self):
        """Hauptschleife des Programms
        Diese def koordiniert alles und stellt die Benutzeroberfläche bereit"""

        #Kosmetische Darstellung des Startes:
        print("\n" + "="*50)
        print("Willkommen beim Karlsruhe ÖPNV-Router!")
        print("="*50)
        
        #Hauptschleife:
        while True:
            try:
                ''' 1. Benutzereingaben'''
                #Verkehrsmittel-Modus abfragen
                transport_mode = self._get_transport_mode()
                if transport_mode is None:
                    continue
                
                #Start und Ziel abfragen
                start_location = self._get_location_input("Start (Adresse oder Haltestelle)")
                if not start_location:
                    continue
                
                end_location = self._get_location_input("Ziel (Adresse oder Haltestelle)")
                if not end_location:
                    continue
                
                '''2. Haltestellen auflösen, wandelt z.B. "Marktplatz" in die konkrete Haltestellen ID um'''
                start_stops, start_walking = self.router._resolve_location(start_location)
                end_stops, end_walking = self.router._resolve_location(end_location)

                #Schutzabfrage, wenn keine Haltestelle gefunden wurde
                if not start_stops:
                    print(f"Keine Haltestellen für '{start_location}' gefunden!")
                    continue

                if not end_stops:
                    print(f"Keine Haltestellen für '{end_location}' gefunden")
                    continue

                ''' 3. Erweiterte Stop-IDs berechnen'''
                # wird um die "child_stops" erweitert.
                # Soll das Problem lösen, wenn User Haltestelle angibt aber diese Haltestelle mehrere Gleise hat
                expanded_start_ids = []
                for stop in start_stops:
                    child_ids = self.gtfs_loader.get_all_child_stop_ids(stop['stop_id'])
                    expanded_start_ids.extend(child_ids)
                
                #Startzeit abfragen
                departure_time = self._get_departure_time()
                if departure_time is None:
                    continue
                
                #DEBUGGING: Ob die Startzeit richtig formatiert und weitergegeben wurde
                print(f"\nVerwendete Startzeit: {self._format_time(departure_time)}")
                
                '''4. Routing durchführen'''
                        #Routing für diese Kombination
                journeys = self.router.find_routes(
                        start_location, 
                        end_location, 
                        departure_time, 
                        transport_mode,
                        max_routes=1
                        )
                
                ''' 5. Ergebnisse anzeigen'''
                self._display_results(journeys)
                
                #Frage ob noch nach weiteren Routen gesucht werden soll
                if not self._ask_continue():
                    break
                    
            except KeyboardInterrupt:
                print("\n\nProgramm beendet.")
                break
            except Exception as e:
                print(f"Fehler: {e}")
                if not self._ask_continue():
                    break

    
    def _get_transport_mode(self) -> Optional[int]:
        """Fragt Verkehrsmittel-Modus ab"""
        while True:
            try:
                print("\nModusauswahl:")
                print("1 - Nur Bahn (S-Bahn, Straßenbahn)")
                print("2 - Bus und Bahn")
                print("0 - Beenden")
                
                choice = input("Geben Sie 1, 2 oder 0 ein: ").strip()
                
                if choice == "0":
                    print("Auf Wiedersehen!")
                    sys.exit(0)
                elif choice in ["1", "2"]:
                    return int(choice)
                else:
                    print("Ungültige Eingabe. Bitte 1, 2 oder 0 eingeben.")
                    
            except (ValueError, KeyboardInterrupt):
                return None
    
    def _get_location_input(self, prompt: str) -> Optional[str]:
        """Fragt Standort ab mit Eingabevalidierung[4]"""
        while True:
            try:
                location = input(f"{prompt}: ").strip()
                if not location:
                    print("Bitte geben Sie einen Ort ein.")
                    continue
                return location
            except KeyboardInterrupt:
                return None
    
    def _get_departure_time(self) -> Optional[timedelta]:
        """Fragt Abfahrtszeit ab mit automatischer Standardzeit[4]"""
        while True:
            try:
                time_input = input("Bitte Startzeit angeben (HH:MM) oder (HH:MM:SS), Enter für jetzt: ").strip()
                
                # Standardmäßig aktuelle Zeit verwenden[4]
                if not time_input:
                    now = datetime.now()
                    return timedelta(hours=now.hour, minutes=now.minute, seconds=now.second)
                
                # Zeit parsen
                time_parts = time_input.split(':')
                if len(time_parts) == 2:
                    hours, minutes = int(time_parts[0]), int(time_parts[1])
                    seconds = 0
                elif len(time_parts) == 3:
                    hours, minutes, seconds = int(time_parts[0]), int(time_parts[1]), int(time_parts[2])
                else:
                    raise ValueError("Ungültiges Zeitformat")
                
                # Validierung
                if not (0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds <= 59):
                    raise ValueError("Ungültige Zeit")
                
                return timedelta(hours=hours, minutes=minutes, seconds=seconds)
                
            except ValueError as e:
                print(f"Ungültige Zeitangabe: {e}")
                print("Bitte verwenden Sie das Format HH:MM oder HH:MM:SS")
            except KeyboardInterrupt:
                return None
    
    def _display_results(self, journeys: list[Journey]):
        """Zeigt Routing-Ergebnisse an"""
        if not journeys:
            print("\nKeine Route gefunden.")
            print("Versuchen Sie es mit anderen Eingaben oder einem späteren Zeitpunkt.")
            return
        
        print(f"\nGefundene Routen ({len(journeys)}):")
        print("="*60)
        
        for i, journey in enumerate(journeys, 1):
            print(f"\n--- Route {i} ---")
            self._display_journey(journey)
    
    def _display_journey(self, journey: Journey):
        """Zeigt eine einzelne Reise an"""
        print(f"Gesamtdauer: {self._format_duration(journey.total_duration)}")
        print(f"Umstiege: {journey.transfers}")
        
        if journey.total_walking_distance > 0:
            print(f"Fußweg gesamt: {journey.total_walking_distance:.0f}m")
        
        print("\nVerbindungen:")
        
        for segment in journey.segments:
            if segment.mode == 'walking':
                self._display_walking_segment(segment)
            else:
                self._display_transit_segment(segment)
    
    def _display_walking_segment(self, segment: RouteSegment):
        """Zeigt Fußweg-Segment an"""
        print(f"Fußweg ({segment.walking_distance:.0f}m)")
        
        if segment.walking_directions:
            for direction in segment.walking_directions:
                print(f"→ {direction}")
        
        if segment.to_stop_name:
            print(f"→ zur Haltestelle: {segment.to_stop_name}")
        elif segment.from_stop_name:
            print(f"→ von Haltestelle: {segment.from_stop_name}")
    
    def _display_transit_segment(self, segment: RouteSegment):
        """Zeigt ÖPNV-Segment an"""
        route_name = segment.route_name or "Unbekannte Linie"
        direction = segment.route_direction or "Unbekannte Richtung"
        
        departure_str = self._format_time(segment.departure_time) if segment.departure_time else "??"
        arrival_str = self._format_time(segment.arrival_time) if segment.arrival_time else "??"
        
        print(f"{route_name} Richtung {direction}")
        print(f"{segment.from_stop_name} → {segment.to_stop_name}")
        print(f"Abfahrt: {departure_str}, Ankunft: {arrival_str}")
    
    def _format_time(self, td: timedelta) -> str:
        """Formatiert timedelta zu HH:MM:SS"""
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def _format_duration(self, td: timedelta) -> str:
        """Formatiert Dauer benutzerfreundlich"""
        total_minutes = int(td.total_seconds() // 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        
        if hours > 0:
            return f"{hours}h {minutes}min"
        else:
            return f"{minutes}min"
    
    def _ask_continue(self) -> bool:
        """Fragt ob weitere Suche gewünscht"""
        try:
            choice = input("\nWeitere Suche? (j/n): ").strip().lower()
            return choice in ['j', 'ja', 'y', 'yes', '']
        except KeyboardInterrupt:
            return False

def main():
    """Hauptfunktion"""
    try:
        router = KarlsruheTransitRouter()      
        router.run()
    except Exception as e:
        print(f"Kritischer Fehler: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
