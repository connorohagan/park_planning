# flood.py
import geopandas as gpd
import numpy as np
import pandas as pd

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
    c["geometry"] = c.geometry.buffer(0)
    c = c[c.geometry.notna() & ~c.geometry.is_empty].copy()
    c["site_area_m2"] = c.geometry.area
    c = c[c["site_area_m2"] > 0].copy() 

    print(f"Flood scoring: {len(c)} candidate sites")

    def prepare_source(flood_gdf):
        if flood_gdf is None or len(flood_gdf) == 0:
            return gpd.GeoDataFrame({"risk_val": [], "geometry": []}, geometry="geometry", crs=getattr(flood_gdf, "crs", None))
        
        f = flood_gdf[["risk_val", "geometry"]].copy()
        f = f[f["risk_val"].notna()].copy()
        f["geometry"] = f.geometry.buffer(0)
        f = f[f.geometry.notna() & ~f.geometry.is_empty].copy()

        if len(f) == 0:
            return gpd.GeoDataFrame({"risk_val": [], "geometry": []}, geometry="geometry", crs=flood_gdf.crs)
        
        f["risk_val"] = f["risk_val"].astype(float)
        return f.sort_values("risk_val", ascending=False).reset_index(drop=True)

    rivers_use = prepare_source(rivers_gdf)
    surface_use = prepare_source(surface_gdf)

    print(f"Prepared rivers flood geometries: {len(rivers_use)}")
    print(f"Prepared surface flood geometries: {len(surface_use)}")

    def area_weighted_source_risk(cand_gdf, flood_gdf, source_name):

        if flood_gdf is None or len(flood_gdf) == 0:
            out = cand_gdf[["cand_id"]].copy()
            out[f"{source_name}_flood_area_m2"] = 0.0
            out[f"{source_name}_flood_percent"] = 0.0
            out[f"{source_name}_risk_0_1"] = 0.0
            return out
        
        sindex = flood_gdf.sindex

        rows = []
        total = len(cand_gdf)
        



        for i, (_, cand_row) in enumerate(cand_gdf[["cand_id", "site_area_m2", "geometry"]].iterrows(), start=1):
            cand_id = cand_row["cand_id"]
            site_area = cand_row["site_area_m2"]
            site_geom = cand_row["geometry"]

            if i % 100 == 0 or i == total:
                print(f"{source_name}: processed {i}/{total} candidate sites")

            # quick bbox filter using the spatial index
            possible_idx = list(sindex.intersection(site_geom.bounds))
            if not possible_idx:
                rows.append({
                    "cand_id": cand_id,
                    f"{source_name}_flood_area_m2": 0.0,
                    f"{source_name}_flood_percent": 0.0,
                    f"{source_name}_risk_0_1": 0.0,
                })
                continue

            nearby = flood_gdf.iloc[possible_idx].copy()
            nearby = nearby[nearby.intersects(site_geom)].copy()

            if len(nearby) == 0:
                rows.append({
                    "cand_id": cand_id,
                    f"{source_name}_flood_area_m2": 0.0,
                    f"{source_name}_flood_percent": 0.0,
                    f"{source_name}_risk_0_1": 0.0,
                })
                continue

            # max severity wins 
            remaining_geom = site_geom
            total_flood_area = 0.0
            total_risk = 0.0

            for risk_val, grp in nearby.groupby("risk_val", sort=False):
                class_union = grp.geometry.union_all()
                if class_union is None or class_union.is_empty:
                    continue

                effective_geom = remaining_geom.intersection(class_union)
                if effective_geom is None or effective_geom.is_empty:
                    continue

                area_m2 = effective_geom.area
                if area_m2 <= 0:
                    continue

                risk_0_1 = min(max(float(risk_val) / 3.0, 0.0), 1.0)
                site_share = area_m2 / site_area

                total_flood_area += area_m2
                total_risk += site_share * risk_0_1

                # remove already counted higher risk area
                remaining_geom = remaining_geom.difference(class_union)
                if remaining_geom is None or remaining_geom.is_empty:
                    break

            flood_percent = min(max(total_flood_area / site_area, 0.0), 1.0)
            total_risk = min(max(total_risk, 0.0), 1.0)

            rows.append({
                "cand_id": cand_id,
                f"{source_name}_flood_area_m2": total_flood_area,
                f"{source_name}_flood_percent": flood_percent,
                f"{source_name}_risk_0_1": total_risk,
            })

        return pd.DataFrame(rows)


    

    rivers_stats = area_weighted_source_risk(c, rivers_use, "rivers")
    surface_stats = area_weighted_source_risk(c, surface_use, "surface")

    c = c.merge(rivers_stats, on="cand_id", how="left")
    c = c.merge(surface_stats, on="cand_id", how="left")

    for col in [
        "rivers_flood_area_m2", "rivers_flood_percent", "rivers_risk_0_1",
        "surface_flood_area_m2", "surface_flood_percent", "surface_risk_0_1",
    ]:
        c[col] = c[col].fillna(0.0)


    # combine sources using a weighted average
    total_weight = float(w_rivers + w_surface)
    if total_weight > 0:
        c["flood_risk_0_1"] = (
            (w_rivers * c["rivers_risk_0_1"]) +
            (w_surface * c["surface_risk_0_1"])
        ) / total_weight
    else:
        c["flood_risk_0_1"] = 0.0

    c["flood_risk_0_1"] = c["flood_risk_0_1"].clip(0, 1)
    c["flood_norm"] = 1.0 - c["flood_risk_0_1"]  # higher is better

    return c
