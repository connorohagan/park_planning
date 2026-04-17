# main.py

import matplotlib.pyplot as plt
import osmnx as ox
import folium
import pandas as pd

from . import config
from .data_loading import get_aoi, load_lsoa_and_population, build_population_grid
from .osm_layers import load_osm_features
from .network_analysis import load_walk_network, greedy_dynamic_select_sites
from .flood import load_flood_layers_wales, compute_flood_penalty
from .scoring import build_candidates, score_candidates
from .folium_python import build_folium_map


def ask_YorN(prompt):
    while True:
        answer = input(prompt).strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Enter Y or N")

def ask_int(prompt, min_value):
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
            if min_value is not None and value < min_value:
                print(f"Enter an int >= {min_value}")
                continue
            return value
        except ValueError:
            print("Enter an int")

def ask_float(prompt, min_value, max_value):
    while True:
        raw = input(prompt).strip()
        try:
            value = float(raw)
            if min_value is not None and value < min_value:
                print(f"enter a number >= {min_value}")
                continue
            if max_value is not None and value > max_value:
                print(f"enter a nunmber <= {max_value}")
                continue
            return value
        except ValueError:
            print("enter a number")

def build_stopping_rules(default_rules: dict):
    print("\nChoose stopping criteria for this run")

    rules = {
        "max_sites": None,
        "target_overall_access_percent": None,
        "target_underserved_recovery_percent": None,
    }

    use_max_sites = ask_YorN(
        f"Use max number of new parks? (Defaults to: {default_rules.get('max_sites')}) - ENTER Y OR N "
    )
    print()
    if use_max_sites:
        default_max = default_rules.get("max_sites", 10)
        raw = input(f"enter max number of sites (default {default_max}) ").strip()
        if raw =="":
            rules["max_sites"] = int(default_max)
        else:
            try:
                rules["max_sites"] = int(raw)
                if rules["max_sites"] < 1:
                    print("using default instead.")
                    rules["max_sites"] = int(default_max)
            except ValueError:
                print("using default instead.")
                rules["max_sites"] = int(default_max)

    print()
    use_overall = ask_YorN("Use target overall accessibility percentage? - ENTER Y OR N ")
    if use_overall:
        rules["target_overall_access_percent"] = ask_float(
            "Enter percentage ",
            min_value=0.0,
            max_value=100.0,
        )
    print()
    use_underserved = ask_YorN("use target underserved recovery percentage? - ENTER Y OR N ")
    if use_underserved:
        rules["target_underserved_recovery_percent"] = ask_float(
            "enter percentage ",
            min_value=0.0,
            max_value=100.0,
        )
    print()
    if all(v is None for v in rules.values()):
        print("\nno criteria selected. using default max_sites.\n")
        rules["max_sites"] = int(default_rules.get("max_sites", 10))
    
    print("stopping rules for this run:", rules)
    return rules


def export_run_csv(preset_name, selected, all_candidates_scored, stop_info, stopping_rules, weights):

    safe_preset = preset_name.replace(" ", "_").lower()

    selected_export = selected.copy()
    if "geometry" in selected_export.columns:
        selected_export["centroid_x"] = selected_export.geometry.centroid.x
        selected_export["centroid_y"] = selected_export.geometry.centroid.y
    selected_columns = ["rank", "cand_id", "score", "demand_total_pop", "demand_underserved_pop", "park_dist_m", "area_m2", "flood_risk_0_1", "flood_norm",
                        "centroid_x", "centroid_y"]
    selected_columns = [c for c in selected_columns if c in selected_export.columns]
    selected_export[selected_columns].to_csv(
        f"outputs/selected_sites/selected_sites_{safe_preset}.csv",
        index=False
    )
    

    if all_candidates_scored is not None and len(all_candidates_scored) > 0:
        all_export = all_candidates_scored.copy()

        if "geometry" in all_export.columns:
            all_export["centroid_x"] = all_export.geometry.centroid.x
            all_export["centroid_y"] = all_export.geometry.centroid.y

        all_columns = [
            "iteration",
            "selected_this_iteration",
            "cand_id",
            "cand_node",
            "score",
            "demand_total_pop",
            "demand_underserved_pop",
            "park_dist_m",
            "area_m2",
            "flood_risk_0_1",
            "flood_norm",
            "demand_total_norm",
            "demand_underserved_norm",
            "park_dist_norm",
            "size_norm",
            "centroid_x",
            "centroid_y"
        ]
        all_columns = [c for c in all_columns if c in all_export.columns]

        all_export[all_columns].to_csv(
            f"outputs/all_candidate_scores/all_candidate_scores_{safe_preset}.csv",
            index=False
        )

    
    # run summary csv
    summary_row = {
        "preset_name": preset_name,
        "preset_desc": weights.get("desc", ""),
        "W_DEMAND_TOTAL": weights.get("W_DEMAND_TOTAL"),
        "W_DEMAND_UNDERSERVED": weights.get("W_DEMAND_UNDERSERVED"),
        "W_PARK_DIST": weights.get("W_PARK_DIST"),
        "W_SIZE": weights.get("W_SIZE"),
        "W_FLOOD": weights.get("W_FLOOD"),
        "max_sites_rule": stopping_rules.get("max_sites"),
        "target_overall_access_percent_rule": stopping_rules.get("target_overall_access_percent"),
        "target_underserved_recovery_percent_rule": stopping_rules.get("target_underserved_recovery_percent"),
        "initial_overall_access_pct": stop_info.get("initial_overall_access_pct"),
        "final_overall_access_percent": stop_info.get("overall_access_percent"),
        "final_underserved_recovery_percent": stop_info.get("underserved_recovery_percent"),
        "sites_selected": stop_info.get("sites_selected"),
        "stopping_criteria_met": " | ".join(
            cond.get("message", "") for cond in stop_info.get("met_conditions", [])
        ) if stop_info.get("met_conditions") else "None",

    }

    pd.DataFrame([summary_row]).to_csv(
        f"outputs/run_summaries/run_summary_{safe_preset}.csv",
        index=False
    )

def main():
    ox.settings.use_cache = True
    ox.settings.log_console = True

    # get first name place from full place name "Cardiff" from "Cardiff, Wales, UK"
    place_name = config.place.split(",")[0].strip()

    #stopping rules
    stopping_rules = build_stopping_rules(config.DEFAULT_STOPPING_RULES)

    # AOI
    _, aoi_geom = get_aoi(config.place, config.CRS_METRIC, config.BUFFER_M, max_radius=config.AOI_RADIUS_CAP_M)

    # LSOA and populations
    lsoa = load_lsoa_and_population(
        config.LSOA_GPKG_PATH,
        config.POP_XLSX_PATH,
        config.POP_SHEET_NAME,
        aoi_geom,
        config.CRS_METRIC
    )

    #  - demand points 100 x 100
    demand_grid_pts = build_population_grid(lsoa, cell_size_m=100.0, return_polys=False)
    demand_grid_poly = build_population_grid(lsoa, cell_size_m=100.0, return_polys=True)
    #demand_grid_poly = demand_grid_poly.nlargest(16000, "population")

    # OSM features
    parks_poly, parking_poly, removed, parking_point = load_osm_features(
        aoi_geom,
        config.CRS_METRIC,
        config.MIN_CAR_PARK_SIZE_m2
    )

    # walk network
    G_proj, edges = load_walk_network(aoi_geom, config.CRS_METRIC)

    # flood
    rivers, surface = load_flood_layers_wales(
        config.WALES_RIVERS_SEA_GPKG,
        config.WALES_SURFACEWATER_GPKG,
        aoi_geom,
        config.CRS_METRIC,
        rivers_map=config.rivers_sea_risk_map,
        surface_map=config.surfacewater_risk_map
    )

    # candidates and demand
    candidates = build_candidates(parking_poly)
    # candidates, lsoa_aug = compute_accessibility_demand(
    #     candidates, parks_poly, lsoa, G_proj, config.WALK_CUTOFF_M
    # )

    # flood penalty
    candidates = compute_flood_penalty(candidates, rivers, surface, config.W_RIVERS, config.W_SURFACE)

    # # score
    # candidates_scored = score_candidates(
    #     candidates,
    #     W_DEMAND_TOTAL=config.W_DEMAND_TOTAL,
    #     W_DEMAND_UNDERSERVED=config.W_DEMAND_UNDERSERVED,
    #     W_PARK_DIST=config.W_PARK_DIST,
    #     W_SIZE=config.W_SIZE,
    #     W_FLOOD=config.W_FLOOD,
    # )

    outputs = []

    for preset_name, W, in config.SCORING_PRESETS.items():
        print(f"\nRunning preset: {preset_name} - {W.get('desc','')}")
        selected, lsoa_aug, stop_info, all_candidates_scored = greedy_dynamic_select_sites(
            candidates,
            parks_poly,
            demand_grid_pts,
            lsoa,
            G_proj,
            walk_cutoff_m=config.WALK_CUTOFF_M,
            stopping_rules=stopping_rules,
            min_site_seperation_m=config.MIN_SITE_SEPERATION_M,
            W_DEMAND_TOTAL=W["W_DEMAND_TOTAL"],
            W_DEMAND_UNDERSERVED=W["W_DEMAND_UNDERSERVED"],
            W_PARK_DIST=W["W_PARK_DIST"],
            W_SIZE=W["W_SIZE"],
            W_FLOOD=W["W_FLOOD"],
        )

        print(f"\nselected sites ({preset_name}):")
        print(selected[[
            "rank", "cand_id","score","demand_total_pop","demand_underserved_pop","park_dist_m","area_m2","flood_risk_0_1"
        ]])
        print("\nstopping summary:")
        print(f" Initial overall accessibility: {stop_info['initial_overall_access_pct']:.2f}%")
        print(f" Sites selected: {stop_info['sites_selected']}")
        print(f" Overall accessibility achieved: {stop_info['overall_access_percent']:.2f}%")
        print(f" Underserved recovery achieved: {stop_info['underserved_recovery_percent']:.2f}%")

        if stop_info["met_conditions"]:
            print(" Stopping criteria met:")
            for cond in stop_info["met_conditions"]:
                print(f" - {cond['message']}")
        else:
            print( " no stopping criteria was met")
        
        export_run_csv(preset_name=preset_name,
                       selected=selected,
                       all_candidates_scored=all_candidates_scored,
                       stop_info=stop_info,
                       stopping_rules=stopping_rules,
                       weights=W,
                       )

        m = build_folium_map(
            aoi_geom=aoi_geom,
            crs_metric=config.CRS_METRIC,
            candidates_scored=selected,
            topN=len(selected),
            lsoa=lsoa_aug,
            parks_poly=parks_poly,
            parking_poly=parking_poly,
            rivers=rivers,
            surface=surface,
            demand_grid_poly=demand_grid_poly,
            G_proj=G_proj,
            walk_cutoff_m=config.WALK_CUTOFF_M,
        )

        output_file = f"output_map_{preset_name}.html"
        m.save(output_file)
        outputs.append((preset_name, output_file))
        print(f"Saved {preset_name} Folium Map")

    index_html = ["<html><body><h2>Preset map outputs</h2><ul>"]
    for preset_name, output_file in outputs:
        desc = config.SCORING_PRESETS[preset_name].get("desc", "")
        index_html.append(f'<li><a href="{output_file}">{preset_name}</a> — {desc}</li>')
    index_html.append("</ul></body></html>")

    with open("output_index.html", "w", encoding="utf-8") as f:
        f.write("\n".join(index_html))


    print("saved: output_index.html")

if __name__ == "__main__":
    main()