from pyrosm import OSM
import pandas as pd

osm_path = "ka_bbbike.osm.pbf"
osm = OSM(osm_path)
buildings = osm.get_buildings()

# Nur Gebäude mit Adresse
buildings = buildings.dropna(subset=["addr:housenumber", "addr:street", "geometry"])

# Mittelpunkt der Geometrie als Koordinate (lat/lon)
buildings["lat"] = buildings.geometry.centroid.y
buildings["lon"] = buildings.geometry.centroid.x

def make_full_address(row):
    parts = [
        str(row.get("addr:street", "")).strip(),
        str(row.get("addr:housenumber", "")).strip(),
        str(row.get("addr:postcode", "")).strip(),
        str(row.get("addr:city", "")).strip()
    ]
    return "{} {}, {} {}".format(parts[0], parts[1], parts[2], parts[3]).strip(", ")

buildings["full_address"] = buildings.apply(make_full_address, axis=1)
df = buildings[["full_address", "lat", "lon"]].drop_duplicates()
df.to_csv("karlsruhe_addresses.csv", index=False)
print(f"{len(df)} Adressen extrahiert und gespeichert.")
