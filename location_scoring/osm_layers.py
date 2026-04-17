# osm_layers.py

import osmnx as ox
import geopandas as gpd
import pandas as pd

def geom_to_wgs(geom, src_crs):
    return gpd.GeoSeries([geom], crs=src_crs).to_crs("EPSG:4326").iloc[0]

def load_osm_features(aoi_geom, crs, min_carpark_m2):

    aoi_wgs = geom_to_wgs(aoi_geom, crs)
    # parks
    parks1 = ox.features.features_from_polygon(aoi_wgs, tags={"leisure": "park"})
    parks2 = ox.features.features_from_polygon(aoi_wgs, tags={"landuse": "recreation_ground"})
    parks = pd.concat([parks1, parks2])
    parks_poly = parks[parks.geometry.type.isin(["Polygon", "MultiPolygon"])].to_crs(crs)
    parks_poly = gpd.clip(parks_poly, aoi_geom)
    parks_poly = parks_poly.drop_duplicates(subset="geometry")

    # car parking
    parking = ox.features.features_from_polygon(aoi_wgs, tags={"amenity": "parking"})
    parking_poly = parking[parking.geometry.type.isin(["Polygon", "MultiPolygon"])].to_crs(crs).copy()
    parking_poly = gpd.clip(parking_poly, aoi_geom)
    parking_poly["area_m2"] = parking_poly.geometry.area

    before = len(parking_poly)
    parking_poly = parking_poly[parking_poly["area_m2"] >= min_carpark_m2].copy()
    after = len(parking_poly)

    removed = parking[parking.geometry.type.isin(["Polygon", "MultiPolygon"])].to_crs(crs).copy()
    removed = gpd.clip(removed, aoi_geom)
    removed["area_m2"] = removed.geometry.area
    removed = removed[removed["area_m2"] < min_carpark_m2]

    parking_point = parking[parking.geometry.type.isin(["Point"])].to_crs(crs)
    parking_point = gpd.clip(parking_point, aoi_geom)

    print(f"Parking polygons before filter: {before}")
    print(f"Parking polygons after  filter (>= {min_carpark_m2} m²): {after}")
    print("Parks polygons:", len(parks_poly))
    print("Parking polygons:", len(parking_poly))
    print("Parking points:", len(parking_point))

    return parks_poly, parking_poly, removed, parking_point