# flood.py
import geopandas as gpd
import numpy as np

def load_flood_layers_wales(rivers_gpkg: str, surface_gpkg: str, aoi_geom, crs: str, rivers_map: dict, surface_map: dict):
    minx, miny, maxx, maxy = aoi_geom.bounds
    rivers = gpd.read_file(rivers_gpkg, bbox=(minx, miny, maxx, maxy)).to_crs(crs)
    surface = gpd.read_file(surface_gpkg, bbox=(minx, miny, maxx, maxy)).to_crs(crs)

    rivers = gpd.clip(rivers, aoi_geom)
    surface = gpd.clip(surface, aoi_geom)

    surface["risk_val"] = surface["Risk"].map(surface_map)
    rivers["risk_val"] = rivers["risk"].map(rivers_map)

    print("flood rivers/sea number:", len(rivers))
    print("flood surface water number:", len(surface))
    print("rivers columns", list(rivers.columns))
    print("surface columns", list(surface.columns))

    return rivers, surface

def compute_flood_penalty(candidates_gdf, rivers_gdf, surface_gdf, w_rivers: float, w_surface: float):
    c = candidates_gdf.copy()
    cand_flood = c[["cand_id", "geometry"]].copy()

    # spatial joins - candidate polygon intersect w flood polygons check
    join_r = gpd.sjoin(cand_flood, rivers_gdf[["risk_val", "geometry"]], predicate="intersects", how="left")
    r_max = join_r.groupby("cand_id")["risk_val"].max().reindex(c["cand_id"]).fillna(0)

    join_s = gpd.sjoin(cand_flood, surface_gdf[["risk_val", "geometry"]], predicate="intersects", how="left")
    s_max = join_s.groupby("cand_id")["risk_val"].max().reindex(c["cand_id"]).fillna(0)

    # normalise risk between 0 and 1
    r_norm = (r_max / 3.0).clip(0, 1)
    s_norm = (s_max / 3.0).clip(0, 1)

    # weighted max - soft penalty
    flood_risk = np.maximum(w_rivers * r_norm, w_surface * s_norm) / max(w_rivers, w_surface)

    c["flood_risk_0_1"] = flood_risk
    c["flood_norm"] = 1.0 - c["flood_risk_0_1"] # higher means better
    return c
