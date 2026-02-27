# network_analysis.py

import osmnx as ox
import numpy as np
import networkx as nx
import geopandas as gpd
from .scoring import score_candidates

def load_walk_network(place: str, crs: str):
    G = ox.graph.graph_from_place(place, network_type="walk")
    G_proj = ox.project_graph(G, to_crs=crs)
    edges = ox.graph_to_gdfs(G_proj, nodes=False, edges=True)
    return G_proj, edges

def compute_accessibility_demand(candidates_gdf, parks_poly, lsoa_gdf, G_proj, walk_cutoff_m: float):
    # parks -> representative points -> nearest nodes
    park_pts = parks_poly.geometry.representative_point()
    park_nodes = ox.distance.nearest_nodes(G_proj, X=park_pts.x.to_numpy(), Y=park_pts.y.to_numpy())
    park_nodes = list(set(park_nodes))

    # lsoa -> representative points -> nearest nodes
    lsoa_pts = lsoa_gdf.geometry.representative_point()
    lsoa_nodes = ox.distance.nearest_nodes(G_proj, X=lsoa_pts.x.to_numpy(), Y=lsoa_pts.y.to_numpy())
    lsoa = lsoa_gdf.copy()
    lsoa["lsoa_node"] = lsoa_nodes

    # distance to nearest park for all nodes
    dist_to_park = nx.multi_source_dijkstra_path_length(G_proj, sources=park_nodes, weight="length")
    lsoa["dist_to_park_m"] = lsoa["lsoa_node"].map(dist_to_park).fillna(np.inf)
    lsoa["is_underserved"] = lsoa["dist_to_park_m"] > walk_cutoff_m

    # pre-aggregrate population per node
    node_pop_total = lsoa.groupby("lsoa_node")["population"].sum().to_dict()
    node_pop_underserved = (
        lsoa[lsoa["is_underserved"]]
        .groupby("lsoa_node")["population"].sum()
        .to_dict()
    )

    # candidates -> representative points -> nearest nodes
    cand_pts = candidates_gdf.geometry.representative_point()
    cand_nodes = ox.distance.nearest_nodes(G_proj, X=cand_pts.x.to_numpy(), Y=cand_pts.y.to_numpy())
    candidates = candidates_gdf.copy()
    candidates["cand_node"] = cand_nodes

    demand_total = []
    demand_underserved = []
    cand_park_dist = []

    for n in candidates["cand_node"]:
        cand_park_dist.append(dist_to_park.get(n, np.inf))

        lengths = nx.single_source_dijkstra_path_length(G_proj, n, cutoff=walk_cutoff_m, weight="length")
        reachable = lengths.keys()

        tot = 0.0
        und = 0.0

        for rn in reachable:
            tot += node_pop_total.get(rn, 0.0)
            und += node_pop_underserved.get(rn, 0.0)

        demand_total.append(tot)
        demand_underserved.append(und)

    candidates["demand_total_pop"] = demand_total
    candidates["demand_underserved_pop"] = demand_underserved
    candidates["park_dist_m"] = cand_park_dist

    return candidates, lsoa

def greedy_dynamic_select_sites(
        candidates_gdf,
        parks_poly,
        lsoa_gdf,
        G_proj,
        *,
        walk_cutoff_m: float,
        k: int,
        min_site_seperation_m: float,
        W_DEMAND_TOTAL: float,
        W_DEMAND_UNDERSERVED: float, 
        W_PARK_DIST: float,
        W_SIZE: float,
        W_FLOOD: float,
):
    # greedy first selection making dynamic re-scoring
    # select a site, treat it as a new park, and update distance to park, underserved, remaining candidates re-scored

    # parks -> nodes
    park_pts = parks_poly.geometry.representative_point()
    park_nodes = ox.distance.nearest_nodes(G_proj, X=park_pts.x.to_numpy(), Y=park_pts.y.to_numpy())
    park_nodes = list(set(park_nodes))

    # lsoa -> nodes
    lsoa_pts = lsoa_gdf.geometry.representative_point()
    lsoa_nodes = ox.distance.nearest_nodes(G_proj, X=lsoa_pts.x.to_numpy(), Y=lsoa_pts.y.to_numpy())
    lsoa = lsoa_gdf.copy()
    lsoa["lsoa_node"] = lsoa_nodes

    # population per node ( totla)
    node_pop_total = lsoa.groupby("lsoa_node")["population"].sum().to_dict()
    lsoa_nodes_set = set(node_pop_total.keys())

    # candidates -> nodes
    cand_pts = candidates_gdf.geometry.representative_point()
    cand_nodes = ox.distance.nearest_nodes(G_proj, X=cand_pts.x.to_numpy(), Y=cand_pts.y.to_numpy())
    candidates = candidates_gdf.copy()
    candidates["cand_node"] = cand_nodes

    # initial dist_to_park for all nodes
    dist_to_park = nx.multi_source_dijkstra_path_length(G_proj, sources=park_nodes, weight="length")

    # underserved nodes tracked at node level
    underserved_nodes = {n for n in lsoa_nodes_set if dist_to_park.get(n, np.inf) > walk_cutoff_m}

    # pre compute each candidates reachable nodes within walk cutoff
    reachable_cache = {}
    demand_total_cache = {}
    for n in candidates["cand_node"]:
        if n in reachable_cache:
            continue
        lengths = nx.single_source_dijkstra_path_length(G_proj, n, cutoff=walk_cutoff_m, weight="length")
        reach_nodes = list(lengths.keys())
        reachable_cache[n] = reach_nodes
        demand_total_cache[n] = float(sum(node_pop_total.get(rn, 0.0) for rn in reach_nodes))
    
    def apply_dynamic_metrics(df):
        df = df.copy()
        df["demand_total_pop"] = df["cand_node"].map(demand_total_cache).astype(float)

        def und(n):
            reach = reachable_cache.get(n, [])
            return float(sum(node_pop_total.get(rn, 0.0) for rn in reach if rn in underserved_nodes))
        
        df["demand_underserved_pop"] = df["cand_node"].map(und)
        df["park_dist_m"] = df["cand_node"].map(lambda n: dist_to_park.get(n, np.inf)).astype(float)
        return df
    
    remaining = candidates.copy()
    selected_rows = []
    excluded_nodes = set()

    while len(selected_rows) < k and len(remaining) > 0:
        # remove min-sep exvluded nodes
        if excluded_nodes:
            remaining = remaining[~remaining["cand_node"].isin(excluded_nodes)].copy()
            if len(remaining) == 0:
                break

        rem_dyn = apply_dynamic_metrics(remaining)
        rem_scored = score_candidates(
            rem_dyn,
            W_DEMAND_TOTAL=W_DEMAND_TOTAL,
            W_DEMAND_UNDERSERVED=W_DEMAND_UNDERSERVED,
            W_PARK_DIST=W_PARK_DIST,
            W_SIZE=W_SIZE,
            W_FLOOD=W_FLOOD,
        )

        best = rem_scored.iloc[0]
        selected_rows.append(best)
        best_node = int(best["cand_node"])

        # update dist_to_park with new park node
        new_dists = nx.single_source_dijkstra_path_length(G_proj, best_node, weight="length")
        for n, d in new_dists.items():
            old = dist_to_park.get(n, np.inf)
            if d < old:
                dist_to_park[n] = d

        # update underserved nodes
        for n, d in new_dists.items():
            if d <= walk_cutoff_m and n in underserved_nodes:
                underserved_nodes.remove(n)

        # enforce min seperation
        if min_site_seperation_m and min_site_seperation_m > 0:
            close = nx.single_source_dijkstra_path_length(
                G_proj, best_node, cutoff=min_site_seperation_m, weight="length"
            )
            excluded_nodes.update(close.keys())

        #remove chosen
        remaining = remaining[remaining["cand_id"] != best["cand_id"]].copy()

    if len(selected_rows) == 0:
        selected = candidates.head(0).copy()
        selected["rank"] = []
    else:
        selected = gpd.GeoDataFrame(selected_rows, crs=candidates.crs).reset_index(drop=True)
        selected["rank"] = selected.index + 1

    # lsoa augmentations
    lsoa["dist_to_park_m"] = lsoa["lsoa_node"].map(dist_to_park).fillna(np.inf)
    lsoa["is_underserved"] = lsoa["dist_to_park_m"] > walk_cutoff_m

    return selected, lsoa
