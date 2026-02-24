# network_analysis.py

import osmnx as ox
import numpy as np
import networkx as nx

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