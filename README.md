# OEPNV-Router-Karlsruhe
Dies hier ist ein Repository für das Informatikprojekt zur Erstellung eines ÖPNV-Router für die Stadt Karlsruhe
Um dieses Programm zu starten führen Sie "main.py" aus

Als Datengrundlage liegen folgende Dateien vor:
ka_bbbike.osm.pbf
karlsruhe_addresses.csv

Bitte laden Sie diese aus dem GitHub Repository herunter.

Der GTFS-Datensatz ist zu groß um auf dem Repository hochgeladen zu werden, deshalb laden Sie diese bitte über folgenden Link herunter:

https://www.kvv.de/fahrplan/fahrplaene/open-data.html

Ändern Sie bitte die Dateipfade in "config.py" falls diese sich nicht verändert haben.
Installieren Sie zusätzlich alle nötigen Datenbanken, hier ist die Terminaleingabe:
pip install pandas, heapq, itertools

Falls Sie selbst die Codedatei "extract_addresses.py" verwenden wollen, müssen Sie eine neue conda Umgebung schaffen und dann über das Terminal in der conda Umgebung pyrosm installieren. Dies ist aber jedoch eigentlich nicht nötig, da schon eine "karlsruhe_addresses.csv" mit diesem Code erstellt wurde und die Datei "extract_addresses.py" nur den Sinn hatte aus der "ka_bbbike.osm.pbf" Adressen zu extrahieren


Erklärung des Programms:

Dieser Router, soll dem User die Möglichkeit bieten eine Adresse oder Haltestelle einzugeben, sowie die Startuhrzeit. 
Anhand dessen wird, falls Adressen eingegeben werden Fußwege zu den nächstgelegenen Haltestellen erstellt.
Weiter wird dann eine Route gesucht und ausgegeben.
