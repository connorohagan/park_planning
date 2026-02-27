# main.py

import matplotlib.pyplot as plt
import osmnx as ox

from . import config
from .data_loading import get_aoi, load_lsoa_and_population
from .osm_layers import load_osm_features
from .network_analysis import load_walk_network, greedy_dynamic_select_sites
from .flood import load_flood_layers_wales, compute_flood_penalty
from .scoring import build_candidates, score_candidates
from .plotting import draw_map

def main():
    ox.settings.use_cache = True
    ox.settings.log_console = True

    # get first name place from full place name "Cardiff" from "Cardiff, Wales, UK"
    place_name = config.place.split(",")[0].strip()

    # AOI
    _, aoi_geom = get_aoi(config.place, config.CRS_METRIC, config.BUFFER_M)

    # LSOA and populations
    lsoa = load_lsoa_and_population(
        config.LSOA_GPKG_PATH,
        config.POP_XLSX_PATH,
        config.POP_SHEET_NAME,
        aoi_geom,
        config.CRS_METRIC
    )

    # OSM features
    parks_poly, parking_poly, removed, parking_point = load_osm_features(
        config.place,
        config.CRS_METRIC,
        config.MIN_CAR_PARK_SIZE_m2
    )

    # walk network
    G_proj, edges = load_walk_network(config.place, config.CRS_METRIC)

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

    selected, lsoa_aug = greedy_dynamic_select_sites(
        candidates,
        parks_poly,
        lsoa,
        G_proj,
        walk_cutoff_m=config.WALK_CUTOFF_M,
        k=config.TOP_K,
        min_site_seperation_m=config.MIN_SITE_SEPERATION_M,
        W_DEMAND_TOTAL=config.W_DEMAND_TOTAL,
        W_DEMAND_UNDERSERVED=config.W_DEMAND_UNDERSERVED,
        W_PARK_DIST=config.W_PARK_DIST,
        W_SIZE=config.W_SIZE,
        W_FLOOD=config.W_FLOOD,
    )

    print(f"\nGreedy-dynamic Top {config.TOP_K} selected sites:")
    print(selected[[
        "rank", "cand_id","score","demand_total_pop","demand_underserved_pop","park_dist_m","area_m2","flood_risk_0_1"
    ]].head(10))

    # zoom bounds for detailed view
    zoom_center_x = 318500
    zoom_center_y = 176500
    zoom_width = 3500
    zoom_bounds = [
        zoom_center_x - (zoom_width/2),
        zoom_center_x + (zoom_width/2),
        zoom_center_y - (zoom_width/2),
        zoom_center_y + (zoom_width/2)
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(24, 12), constrained_layout=True)

    draw_map(
        ax1,
        aoi_geom=aoi_geom, edges=edges, lsoa=lsoa_aug,
        parks_poly=parks_poly, parking_poly=parking_poly, removed=removed, parking_point=parking_point,
        rivers=rivers, surface=surface,
        candidates_scored=selected,
        purples_dark=config.purples_dark,
        crs_metric=config.CRS_METRIC,
        zoom_bounds=zoom_bounds, is_zoomed=False,
        topN=10,
        title_full="Full {place_name} View",
        title_zoom="Detailed {place_name} View"
    )

    draw_map(
        ax2,
        aoi_geom=aoi_geom, edges=edges, lsoa=lsoa_aug,
        parks_poly=parks_poly, parking_poly=parking_poly, removed=removed, parking_point=parking_point,
        rivers=rivers, surface=surface,
        candidates_scored=selected,
        purples_dark=config.purples_dark,
        crs_metric=config.CRS_METRIC,
        zoom_bounds=zoom_bounds, is_zoomed=True,
        topN=10,
        title_full="Full Cardiff View",
        title_zoom="Detailed View"
    )

    plt.show()

if __name__ == "__main__":
    main()