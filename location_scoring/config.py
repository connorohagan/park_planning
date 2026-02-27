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
TOP_K = 10
# minimum distance between the suggested sites
MIN_SITE_SEPERATION_M = WALK_CUTOFF_M * 0.75

# scoring weights
W_DEMAND_TOTAL = 0.45
W_DEMAND_UNDERSERVED = 0.20
W_PARK_DIST = 0.15
W_SIZE = 0.10
W_FLOOD = 0.10

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
