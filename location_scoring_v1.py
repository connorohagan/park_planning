import osmnx as ox
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
from matplotlib import cm, colors
import networkx as nx

purples_dark = colors.LinearSegmentedColormap.from_list(
    "purples_dark",
    cm.Purples(np.linspace(0.75, 1.0, 256))
)

LSOA_GPKG_PATH = r"C:\Users\conno\park_planning\data\Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BGC_V5_-6970154227154374572.gpkg"
POP_XLSX_PATH  = r"C:\Users\conno\park_planning\data\sapelsoabroadage20222024.xlsx"
POP_SHEET_NAME = "Mid-2024 LSOA 2021"

# wales flood layers
WALES_RIVERS_SEA_GPKG = r"C:\Users\conno\park_planning\data\flood_data\Wales\NRW_FLOODZONE_RIVERS_SEAS_MERGED.gpkg"
WALES_SURFACEWATER_GPKG = r"C:\Users\conno\park_planning\data\flood_data\Wales\NRW_FLOOD_RISK_FROM_SURFACE_WATER_SMALL_WATERCOURSES.gpkg"

place = "Cardiff, Wales, UK"
# set CRS
CRS_METRIC = "EPSG:27700"  
BUFFER_M = 1500

MIN_CAR_PARK_SIZE_m2 = 500

ox.settings.use_cache = True
ox.settings.log_console = True

# LSOA and population density
lsoa = gpd.read_file(LSOA_GPKG_PATH).to_crs(CRS_METRIC)

cardiff = ox.geocode_to_gdf(place).to_crs(CRS_METRIC)
cardiff_geom = cardiff.geometry.iloc[0]
if cardiff_geom.geom_type == "Point":
    cardiff_geom = cardiff_geom.buffer(6000)
cardiff_geom = cardiff_geom.buffer(BUFFER_M).buffer(0)

lsoa_cardiff = lsoa[lsoa.intersects(cardiff_geom)].copy()

pop = pd.read_excel(POP_XLSX_PATH, sheet_name=POP_SHEET_NAME, header=3)
pop = pop[["LSOA 2021 Code", "Total"]].rename(columns={"LSOA 2021 Code": "LSOA21CD", "Total": "population"})
lsoa_cardiff = lsoa_cardiff.merge(pop, on="LSOA21CD", how="left")

# convert to metres
lsoa_cardiff["area_km2"] = lsoa_cardiff.geometry.area / 1_000_000
lsoa_cardiff["pop_density"] = lsoa_cardiff["population"] / lsoa_cardiff["area_km2"]


# parks polygons
parks1 = ox.features.features_from_place(place, tags={"leisure": "park"})
parks2 = ox.features.features_from_place(place, tags={"landuse": "recreation_ground"})
parks = pd.concat([parks1, parks2])
parks_poly = parks[parks.geometry.type.isin(["Polygon", "MultiPolygon"])].to_crs(CRS_METRIC)
parks_poly = parks_poly.drop_duplicates(subset="geometry")


# car parking 
parking = ox.features.features_from_place(place, tags={"amenity": "parking"})
parking_poly = parking[parking.geometry.type.isin(["Polygon", "MultiPolygon"])].to_crs(CRS_METRIC)

parking_poly = parking_poly.copy()
parking_poly["area_m2"] = parking_poly.geometry.area

before = len(parking_poly)
parking_poly = parking_poly[parking_poly["area_m2"] >= MIN_CAR_PARK_SIZE_m2].copy()
after = len(parking_poly)
print(f"Parking polygons before area filter: {before}")
print(f"Parking polygons after  area filter (>= {MIN_CAR_PARK_SIZE_m2} m²): {after}")

removed = parking[parking.geometry.type.isin(["Polygon", "MultiPolygon"])].to_crs(CRS_METRIC).copy()
removed["area_m2"] = removed.geometry.area
removed = removed[removed["area_m2"] < MIN_CAR_PARK_SIZE_m2]

parking_point = parking[parking.geometry.type.isin(["Point"])].to_crs(CRS_METRIC)

print("Parks polygons:", len(parks_poly))
print("Parking polygons:", len(parking_poly))
print("Parking points:", len(parking_point))

# walk network
G = ox.graph.graph_from_place(place, network_type="walk")
G_proj = ox.project_graph(G, to_crs=CRS_METRIC)
edges = ox.graph_to_gdfs(G_proj, nodes=False, edges=True)

# flood layers - wales
minx, miny, maxx, maxy = cardiff_geom.bounds

rivers_sea = gpd.read_file(WALES_RIVERS_SEA_GPKG, bbox=(minx, miny, maxx, maxy)).to_crs(CRS_METRIC)
surfacewater = gpd.read_file(WALES_SURFACEWATER_GPKG, bbox=(minx, miny, maxx, maxy)).to_crs(CRS_METRIC)
# clip to AOI
rivers_sea = gpd.clip(rivers_sea, cardiff_geom)
surfacewater = gpd.clip(surfacewater, cardiff_geom)

print("flood rivers/sea number:", len(rivers_sea))
print("flood surface water number:", len(surfacewater))
print("rivers sea columns", list(rivers_sea.columns))
print("surfacewater columns", list(surfacewater.columns))

surfacewater_risk_map = {"Low": 1, "Medium": 2, "High": 3}
rivers_sea_risk_map = {"Flood Zone 2": 2, "Flood Zone 3": 3}

surfacewater["risk_val"] = surfacewater["Risk"].map(surfacewater_risk_map)
rivers_sea["risk_val"] = rivers_sea["risk"].map(rivers_sea_risk_map)

print("AOI CRS:", CRS_METRIC)
print("Surfacewater CRS:", surfacewater.crs)
print("Rivers/sea CRS:", rivers_sea.crs)
print("Surfacewater bounds:", surfacewater.total_bounds)
print("AOI bounds:", cardiff_geom.bounds)


# parameters - edit these later if don't seem right
WALK_CUTOFF_M = 800

# scoring weights
W_DEMAND_TOTAL = 0.45
W_DEMAND_UNDERSERVED = 0.20
W_PARK_DIST = 0.15
W_SIZE = 0.10
W_FLOOD = 0.10

W_RIVERS = 1.1
W_SURFACE = 0.9

def minmax(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    mn, mx = s.min(), s.max()
    if pd.isna(mn) or pd.isna(mx) or mx == mn:
        return pd.Series(0.0, index=s.index)
    return (s-mn) / (mx - mn)

# build candidate GeoDataFrame

candidates = parking_poly.copy()
candidates = candidates.reset_index(drop=True)
candidates["cand_id"] = candidates.index
candidates["area_m2"] = candidates.geometry.area

# representative points
cand_pts = candidates.geometry.representative_point()
cand_x = cand_pts.x.to_numpy()
cand_y = cand_pts.y.to_numpy()

# prep park nodes and LSOA centroid nodes
# parks -> represenatitve points -> nearest graph nodes
park_pts = parks_poly.geometry.representative_point()
park_nodes = ox.distance.nearest_nodes(G_proj, X=park_pts.x.to_numpy(), Y=park_pts.y.to_numpy())
park_nodes = list(set(park_nodes))

#LSOA centroids -> nearest graph nodes
lsoa_cent = lsoa_cardiff.geometry.representative_point()
lsoa_nodes = ox.distance.nearest_nodes(G_proj, X=lsoa_cent.x.to_numpy(), Y=lsoa_cent.y.to_numpy())
lsoa_cardiff = lsoa_cardiff.copy()
lsoa_cardiff["lsoa_node"] = lsoa_nodes
lsoa_cardiff["population"] = lsoa_cardiff["population"].fillna(0).astype(float)


# distance to nearest park for all nodes

# for each node, shortest-path distancee to closest park node
dist_to_park = nx.multi_source_dijkstra_path_length(G_proj, sources=park_nodes, weight="length")

#attach park distance to each LSOA centroid node (if node missing, set to inf)
lsoa_cardiff["dist_to_park_m"] = lsoa_cardiff["lsoa_node"].map(dist_to_park).fillna(np.inf)

# underserved LSOAs (currently not within 800m of any park)
lsoa_cardiff["is_underserved"] = lsoa_cardiff["dist_to_park_m"] > WALK_CUTOFF_M



# pre-aggregrate LSOA population by node (trying to speed up summing)
node_pop_total = lsoa_cardiff.groupby("lsoa_node")["population"].sum().to_dict()
node_pop_underserved = (
    lsoa_cardiff[lsoa_cardiff["is_underserved"]]
    .groupby("lsoa_node")["population"].sum()
    .to_dict()
)



# for each candidate, compute reachable nodes within the walkable limit, the sum populations
cand_nodes = ox.distance.nearest_nodes(G_proj, X=cand_x, Y=cand_y)
candidates["cand_node"] = cand_nodes

demand_total = []
demand_underserved = []
cand_park_dist = []

for n in candidates["cand_node"]:
    # underserved bonus component: how far is this candidate from nearest existing green space
    cand_park_dist.append(dist_to_park.get(n, np.inf))

    #nodes reachable within cutoff distance along the walk network
    lengths = nx.single_source_dijkstra_path_length(G_proj, n, cutoff=WALK_CUTOFF_M, weight="length")
    reachable_nodes = lengths.keys()

    # sum populations of LSOA centroid nodes that fall in reachable nodes
    tot = 0.0
    und = 0.0
    for rn in reachable_nodes:
        tot += node_pop_total.get(rn, 0.0)
        und += node_pop_underserved.get(rn, 0.0)

    demand_total.append(tot)
    demand_underserved.append(und)

candidates["demand_total_pop"] = demand_total
candidates["demand_underserved_pop"] = demand_underserved
candidates["park_dist_m"] = cand_park_dist
candidates["underserved_share"] = np.where(
    candidates["demand_total_pop"] > 0,
    candidates["demand_underserved_pop"] / candidates["demand_total_pop"],
    0.0
)


# flood penalty per candidate

# intersect each candidate with flood polygons and take MAX risk_val
cand_flood = candidates[["cand_id", "geometry"]].copy()

# river/sea max risk_val per candidate
join_r = gpd.sjoin(cand_flood, rivers_sea[["risk_val", "geometry"]], predicate="intersects", how="left")
r_max = join_r.groupby("cand_id")["risk_val"].max().reindex(candidates["cand_id"]).fillna(0)

# surface water max risk_val per candidate
join_s = gpd.sjoin(cand_flood, surfacewater[["risk_val", "geometry"]], predicate="intersects", how="left")
s_max = join_s.groupby("cand_id")["risk_val"].max().reindex(candidates["cand_id"]).fillna(0)

# normalize to 0..1 then weighted-max combine
r_norm = (r_max / 3.0).clip(0, 1)
s_norm = (s_max / 3.0).clip(0, 1)

flood_combined = np.maximum(W_RIVERS * r_norm, W_SURFACE * s_norm) / max(W_RIVERS, W_SURFACE)
candidates["flood_risk_0_1"] = flood_combined
candidates["flood_penalty_0_1"] = 1.0 - candidates["flood_risk_0_1"]



# normalise indicators and weighted sum score

candidates["demand_total_norm"] = minmax(candidates["demand_total_pop"])
candidates["demand_underserved_norm"] = minmax(candidates["demand_underserved_pop"])
candidates["park_dist_norm"] = minmax(candidates["park_dist_m"].replace(np.inf, np.nan).fillna(candidates["park_dist_m"][candidates["park_dist_m"] != np.inf].max()))
candidates["size_norm"] = minmax(np.log1p(candidates["area_m2"]))

#flood penalty already 0 to 1 but keep higher = better
candidates["flood_norm"] = candidates["flood_penalty_0_1"].astype(float)

candidates["score"] = (
    W_DEMAND_TOTAL * candidates["demand_total_norm"]
    + W_DEMAND_UNDERSERVED * candidates["demand_underserved_norm"]
    + W_PARK_DIST * candidates["park_dist_norm"]
    + W_SIZE * candidates["size_norm"]
    + W_FLOOD * candidates["flood_norm"]
)

candidates_scored = candidates.sort_values("score", ascending=False).copy()

print("\nTop 10 candidate sites by score:")
print(candidates_scored[["cand_id", "score", "demand_total_pop", "demand_underserved_pop", "park_dist_m", "area_m2", "flood_risk_0_1"]].head(10))



# --- SET ZOOM PARAMETERS ---
# Cardiff Center approx: Easting 319000, Northing 176000
zoom_center_x = 318500 
zoom_center_y = 176500
zoom_width = 3500  # 3km wide view

zoom_bounds = [
    zoom_center_x - (zoom_width/2), # xmin
    zoom_center_x + (zoom_width/2), # xmax
    zoom_center_y - (zoom_width/2), # ymin
    zoom_center_y + (zoom_width/2)  # ymax
]


def draw_map(ax_obj, is_zoomed=False):


    if len(rivers_sea) > 0:
        rivers_sea.sort_values("risk_val").plot(
            ax=ax_obj,
            column="risk_val",
            cmap="Blues",
            alpha=0.8,
            linewidth=0,
            edgecolor="none",
            vmin=1, vmax=3.5,
            legend=False
        )

    if len(surfacewater) > 0:
        surfacewater.sort_values("risk_val").plot(
            ax=ax_obj,
            column="risk_val",
            cmap=purples_dark,
            alpha=0.8,
            linewidth=0.2,
            edgecolor="purple",
            legend=False
        )
    # population density
    lsoa_cardiff.plot(ax=ax_obj, column="pop_density", cmap="YlOrRd", legend=False, alpha=0.75, linewidth=0.0)

    # walk network
    edges.plot(ax=ax_obj, linewidth=0.35, alpha=0.6, color="black")

    # parks set to green
    if len(parks_poly) > 0:
        parks_poly.plot(ax=ax_obj, alpha=0.75, color="limegreen", edgecolor="darkgreen", linewidth=0.5)

    # parking polygons grey
    if len(parking_poly) > 0:
        parking_poly.plot(ax=ax_obj, alpha=0.55, color="none", edgecolor="fuchsia", hatch="////", linewidth=1.0)

    removed.plot(ax=ax_obj, color="red", edgecolor="darkred", alpha=0.8, linewidth=0.5, label="removed")

    topN = 10
    top = candidates_scored.head(topN)

    # inside draw_map(), after parking_poly plotting:
    top = top.copy()
    top["pt"] = top.geometry.representative_point()
    gpd.GeoSeries(top["pt"], crs=top.crs).plot(
        ax=ax_obj,
        color="cyan",
        markersize=120,
        alpha=0.95,
        edgecolor="black",
        linewidth=1.2,
        zorder=55
    )
    top = top.sort_values("score", ascending=False).reset_index(drop=True)
    for i, row in top.iterrows():
        ax_obj.annotate(
            text=str(i+1),
            xy=(row["pt"].x, row["pt"].y),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize = 12,
            fontweight="bold",
            color="black",
            zorder=60

        )

    # parking points white
    if len(parking_point) > 0:
        parking_point.plot(ax=ax_obj, markersize=10, alpha=0.85, color="gold", edgecolor="black", linewidth=0.6)


    gpd.GeoSeries([cardiff_geom], crs=CRS_METRIC).boundary.plot(ax=ax_obj, linewidth=2.0, color="black")

    if is_zoomed:
        ax_obj.set_xlim(zoom_bounds[0], zoom_bounds[1])
        ax_obj.set_ylim(zoom_bounds[2], zoom_bounds[3])
        ax_obj.set_title("Detailed View", fontsize=20, pad=20)
    else:
        bounds = cardiff_geom.bounds # [minx, miny, maxx, maxy]
        ax_obj.set_xlim(bounds[0], bounds[2])
        ax_obj.set_ylim(bounds[1], bounds[3])
        ax_obj.set_title("Full Cardiff View", fontsize=20, pad=20)

    ax_obj.axis("off")


fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(24, 12), constrained_layout=True) 
# CALL the function for the first axis
draw_map(ax1, is_zoomed=False)

# CALL the function for the second axis
draw_map(ax2, is_zoomed=True)
print("Rivers/sea risk bands:", rivers_sea["risk"].value_counts().head(20))
print("Surface water risk bands:", surfacewater["Risk"].value_counts().head(20))

#plt.title("cardiff: population density + walk networks + parks + car parks + flood")
plt.axis("off")
plt.show()

