# data_loading.py

import osmnx as ox
import geopandas as gpd
import pandas as pd
import numpy as np

def get_aoi(place: str, crs: str, buffer_m: float):
    aoi_gdf = ox.geocode_to_gdf(place).to_crs(crs)
    geom = aoi_gdf.geometry.iloc[0]
    if geom.geom_type == "Point":
        geom = geom.buffer(6000)
    geom = geom.buffer(buffer_m).buffer(0)
    return aoi_gdf, geom

def load_lsoa_and_population(lsoa_gpkg: str, pop_xlsx: str, pop_sheet: str, aoi_geom, crs: str):
    lsoa = gpd.read_file(lsoa_gpkg).to_crs(crs)
    lsoa_city = lsoa[lsoa.intersects(aoi_geom)].copy()

    pop = pd.read_excel(pop_xlsx, sheet_name=pop_sheet, header=3)
    pop = pop[["LSOA 2021 Code", "Total"]].rename(columns={"LSOA 2021 Code": "LSOA21CD", "Total": "population"})
    lsoa_city = lsoa_city.merge(pop, on="LSOA21CD", how="left")

    lsoa_city["population"] = lsoa_city["population"].fillna(0).astype(float)
    lsoa_city["area_km2"] = lsoa_city.geometry.area / 1_000_000
    lsoa_city["pop_density"] = np.where(
        lsoa_city["area_km2"] > 0,
        lsoa_city["population"] / lsoa_city["area_km2"],
        0.0
    )
    return lsoa_city