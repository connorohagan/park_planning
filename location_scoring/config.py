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

# cap on AOI size around the geocoded place centre
AOI_RADIUS_CAP_M = None 

# candidate exclusions
MIN_CAR_PARK_SIZE_m2 = 500

# network cut-off
WALK_CUTOFF_M = 800

# selection for greedy algorithm
# TOP_K = 10 delete this if plan works

DEFAULT_STOPPING_RULES = {
    "max_sites": 30,
    "target_overall_access_percent": None,
    "target_underserved_recovery_percent": None,
}
# minimum distance between the suggested sites
MIN_SITE_SEPERATION_M = WALK_CUTOFF_M * 0.75

DEFAULT_PRESET = "balanced"

SCORING_PRESETS = {
    # balanced default
    "balanced": {
        "desc": "General-purpose trade-off: Balanced weights.",
        "W_DEMAND_TOTAL": 0.20,
        "W_DEMAND_UNDERSERVED": 0.20,
        "W_PARK_DIST": 0.20,
        "W_SIZE": 0.20,
        "W_FLOOD": 0.20,
    },

    # Puts parks where lots of people can benefit (regardless of if they currently have access)
    "demand_focused": {
        "desc": "Demand focused: Benefit maximum number of residents.",
        "W_DEMAND_TOTAL": 0.50,
        "W_DEMAND_UNDERSERVED": 0.10,
        "W_PARK_DIST": 0.10,
        "W_SIZE": 0.15,
        "W_FLOOD": 0.15,
    },

    # Strongly targets areas lacking access to parks
    "gap_coverage": {
        "desc": "Close green-space gaps: underserved demand dominated, with high park distance.",
        "W_DEMAND_TOTAL": 0.10,
        "W_DEMAND_UNDERSERVED": 0.50,
        "W_PARK_DIST": 0.20,
        "W_SIZE": 0.10,
        "W_FLOOD": 0.10,
    },

    # Focuses on improving accessibility by reducing distance-to-park
    "accessibility_focused": {
        "desc": "Focused on reducing distance to nearest park.",
        "W_DEMAND_TOTAL": 0.20,
        "W_DEMAND_UNDERSERVED": 0.20,
        "W_PARK_DIST": 0.40,
        "W_SIZE": 0.10,
        "W_FLOOD": 0.10,
    },

    # Conservative: strongly avoid flood risk still respects demand
    "safety_first": {
        "desc": "Safety first: avoid flood risk.",
        "W_DEMAND_TOTAL": 0.15,
        "W_DEMAND_UNDERSERVED": 0.15,
        "W_PARK_DIST": 0.10,
        "W_SIZE": 0.10,
        "W_FLOOD": 0.50,
    },

    # Quick wins / feasibility: prefers larger sites and avoid flood risk
    "feasibility_first": {
        "desc": "Feasibility focused - both size and avoid flood risk.",
        "W_DEMAND_TOTAL": 0.10,
        "W_DEMAND_UNDERSERVED": 0.10,
        "W_PARK_DIST": 0.10,
        "W_SIZE": 0.40,
        "W_FLOOD": 0.30,
    },
}

# flood combination
W_RIVERS = 1.1
W_SURFACE = 0.9

# flood risk values mapping
surfacewater_risk_map = {"Low": 1, "Medium": 2, "High": 3}
rivers_sea_risk_map = {"Flood Zone 2": 2, "Flood Zone 3": 3}

# extra colours
purples_dark = colors.LinearSegmentedColormap.from_list(
    "purples_dark",
    cm.Purples(np.linspace(0.75, 1.0, 256))
)
