# data_loading.py

import osmnx as ox
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import box

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

def build_population_grid(
        lsoa_city: gpd.GeoDataFrame,
        *,
        cell_size_m: float = 100.0,
        pop_col: str = "population",
        id_col: str = "LSOA21CD",
        return_polys: bool,
) -> gpd.GeoDataFrame:
    
    if lsoa_city.empty:
        return gpd.GeoDataFrame({"grid_id": [], pop_col: []}, geometry=[], crs=lsoa_city.crs)
    
    if pop_col not in lsoa_city.columns:
        raise ValueError(f"Expeceted '{pop_col}' column in lsoa city")
    
    # clean geometries 
    lsoa = lsoa_city[[id_col, pop_col, "geometry"]].copy()
    lsoa["geometry"] = lsoa.geometry.buffer(0)
    lsoa[pop_col] = lsoa[pop_col].fillna(0).astype(float)

    # get LSOA areas for percentage allocations
    lsoa["lsoa_area_m2"] = lsoa.geometry.area
    lsoa = lsoa[lsoa["lsoa_area_m2"] > 0].copy()
    if lsoa.empty:
        return gpd.GeoDataFrame({"grid_id": [], pop_col: []}, geometry=[], crs=lsoa_city.crs)
    
    # union lsoa polyogns together
    lsoa_union = lsoa.unary_union

    # building grids over lsoa union  boundaryies

    minx, miny, maxx, maxy = lsoa_union.bounds
    xs = np.arange(minx, maxx + cell_size_m, cell_size_m)
    ys = np.arange(miny, maxy + cell_size_m, cell_size_m)

    grid_polys = []

    grid_ids = []
    gid = 0
    for x in xs[:-1]:
        for y in ys[:-1]:
            cell = box(x, y, x + cell_size_m, y + cell_size_m)
            if cell.intersects(lsoa_union):
                grid_polys.append(cell)
                grid_ids.append(gid)
                gid += 1

    
    grid = gpd.GeoDataFrame({"grid_id": grid_ids}, geometry=grid_polys, crs=lsoa.crs)

    if grid.empty:
        return gpd.GeoDataFrame({"grid_id": [], pop_col: []}, geometry=[], crs=lsoa_city.crs)
    
    # intersection
    inter = gpd.overlay(
        grid,
        lsoa[[id_col, pop_col, "lsoa_area_m2", "geometry"]],
        how="intersection",
        keep_geom_type=False
    )

    inter["inter_area_m2"] = inter.geometry.area

    inter["pop_part"] = inter[pop_col] * (inter["inter_area_m2"] / inter["lsoa_area_m2"])

    # summing allocated pops to each grid cell
    pop_by_cell = inter.groupby("grid_id")["pop_part"].sum().reset_index()
    pop_by_cell = pop_by_cell.rename(columns={"pop_part": pop_col})

    #join back to full grid
    grid2 = grid.merge(pop_by_cell, on="grid_id", how="left")
    grid2[pop_col] = grid2[pop_col].fillna(0.0).astype(float)

    # retrn centroid points
    # pts = grid2.copy()
    # pts["geometry"] = pts.geometry.centroid
    # pts = pts[pts[pop_col] > 0].copy()

    # if return_polys:
    #     return pts[["grid_id", pop_col, "geometry"]]

    # pts = grid2.copy()
    # pts["geometry"] = pts.geometry.centroid
    # pts = pts[pts[pop_col] > 0 ].copy()
    # return pts[["grid_id", pop_col, "geometry"]]

    if return_polys:
        grid_poly = grid2[grid2[pop_col] > 0].copy()
        return grid_poly[["grid_id", pop_col, "geometry"]]
    pts = grid2.copy()
    pts["geometry"] = pts.geometry.centroid
    pts = pts[pts[pop_col] > 0].copy()
    return pts[["grid_id", pop_col, "geometry"]]