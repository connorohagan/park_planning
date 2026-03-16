# config.py

from matplotlib import cm, colors
import numpy as np


# Paths
LSOA_GPKG_PATH = r"C:\Users\conno\park_planning\data\Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BGC_V5_-6970154227154374572.gpkg"
POP_XLSX_PATH  = r"C:\Users\conno\park_planning\data\sapelsoabroadage20222024.xlsx"
POP_SHEET_NAME = "Mid-2024 LSOA 2021"

WALES_RIVERS_SEA_GPKG = r"C:\Users\conno\park_planning\data\flood_data\Wales\NRW_FLOODZONE_RIVERS_SEAS_MERGED.gpkg"
WALES_SURFACEWATER_GPKG = r"C:\Users\conno\park_planning\data\flood_data\Wales\NRW_FLOOD_RISK_FROM_SURFACE_WATER_SMALL_WATERCOURSES.gpkg"

# set place
place = "Cardiff, Wales, UK"

# set CRS
CRS_METRIC = "EPSG:27700"  
BUFFER_M = 1500

# candidate exclusions
MIN_CAR_PARK_SIZE_m2 = 500

# network cut-off
WALK_CUTOFF_M = 800

# selection for greedy algorithm
# TOP_K = 10 delete this if plan works

DEFAULT_STOPPING_RULES = {
    "max_sites": 10,
    "target_overall_access_percent": None,
    "target_underserved_recovery_percent": None,
}
# minimum distance between the suggested sites
MIN_SITE_SEPERATION_M = WALK_CUTOFF_M * 0.75

DEFAULT_PRESET = "balanced"

SCORING_PRESETS = {
    # Good default: demand-led but still risk/feasibility aware
    "balanced": {
        "desc": "General-purpose trade-off: demand-led, equity-aware, avoids risky/small sites.",
        "W_DEMAND_TOTAL": 0.30,
        "W_DEMAND_UNDERSERVED": 0.20,
        "W_PARK_DIST": 0.15,
        "W_SIZE": 0.15,
        "W_FLOOD": 0.20,
    },

    # Puts parks where lots of people can benefit (regardless of current provision)
    "demand_focused": {
        "desc": "Maximise overall benefit to residents (total demand dominates).",
        "W_DEMAND_TOTAL": 0.50,
        "W_DEMAND_UNDERSERVED": 0.10,
        "W_PARK_DIST": 0.10,
        "W_SIZE": 0.15,
        "W_FLOOD": 0.15,
    },

    # Strongly targets areas lacking access to parks
    "gap_coverage": {
        "desc": "Close green-space gaps: underserved demand dominates, then park-distance.",
        "W_DEMAND_TOTAL": 0.15,
        "W_DEMAND_UNDERSERVED": 0.45,
        "W_PARK_DIST": 0.20,
        "W_SIZE": 0.10,
        "W_FLOOD": 0.10,
    },

    # Focuses on improving accessibility by reducing distance-to-park
    "accessibility_focused": {
        "desc": "Prioritise reducing distance to nearest park (network accessibility).",
        "W_DEMAND_TOTAL": 0.20,
        "W_DEMAND_UNDERSERVED": 0.20,
        "W_PARK_DIST": 0.35,
        "W_SIZE": 0.10,
        "W_FLOOD": 0.15,
    },

    # Conservative: strongly avoid flood risk, still respects demand
    "safety_first": {
        "desc": "Minimise flood exposure: flood risk dominates selection.",
        "W_DEMAND_TOTAL": 0.20,
        "W_DEMAND_UNDERSERVED": 0.15,
        "W_PARK_DIST": 0.10,
        "W_SIZE": 0.10,
        "W_FLOOD": 0.45,
    },

    # Quick wins / feasibility: prefers larger sites (and avoids flood), less strict on coverage
    "feasibility_first": {
        "desc": "Favour sites that are easier to deliver: size + flood dominate.",
        "W_DEMAND_TOTAL": 0.15,
        "W_DEMAND_UNDERSERVED": 0.10,
        "W_PARK_DIST": 0.10,
        "W_SIZE": 0.40,
        "W_FLOOD": 0.25,
    },
}

# flood combination
W_RIVERS = 1.2
W_SURFACE = 0.8

# flood risk values mapping
surfacewater_risk_map = {"Low": 1, "Medium": 2, "High": 3}
rivers_sea_risk_map = {"Flood Zone 2": 2, "Flood Zone 3": 3}

# extra colours
purples_dark = colors.LinearSegmentedColormap.from_list(
    "purples_dark",
    cm.Purples(np.linspace(0.75, 1.0, 256))
)
