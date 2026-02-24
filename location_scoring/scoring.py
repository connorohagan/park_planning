# scoring.py

import numpy as np
from .utils import minmax

def build_candidates(parking_poly):
    c = parking_poly.copy().reset_index(drop=True)
    c["cand_id"] = c.index
    c["area_m2"] = c.geometry.area
    return c

def score_candidates(candidates, *, W_DEMAND_TOTAL: float, W_DEMAND_UNDERSERVED: float, W_PARK_DIST: float, W_SIZE: float, W_FLOOD: float):
    c = candidates.copy()

    c["demand_total_norm"] = minmax(c["demand_total_pop"])
    c["demand_underserved_norm"] = minmax(c["demand_underserved_pop"])

    park_dist_series = c["park_dist_m"].replace(np.inf, np.nan)
    fallback = park_dist_series.max(skipna=True)
    c["park_dist_norm"] = minmax(park_dist_series.fillna(fallback))

    c["size_norm"] = minmax(np.log1p(c["area_m2"]))

    # flood_norm already in 0 to 1
    c["score"] = (
        W_DEMAND_TOTAL * c["demand_total_norm"]
        + W_DEMAND_UNDERSERVED * c["demand_underserved_norm"]
        + W_PARK_DIST * c["park_dist_norm"]
        + W_SIZE * c["size_norm"]
        + W_FLOOD * c["flood_norm"]
    )

    return c.sort_values("score", ascending=False).reset_index(drop=True)