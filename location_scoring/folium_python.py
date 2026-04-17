# folium_python.py

import folium
import geopandas as gpd
import numpy as np
import networkx as nx
from shapely.geometry import LineString
from branca.colormap import linear
from folium.features import DivIcon

from geopy.geocoders import Nominatim
import time

CRS_WEB = "EPSG:4326"

GEOLOCATOR = Nominatim(user_agent="site_suitability_analysis_v1")

def get_postcode(lat: float, lon: float) -> str:
    # helper function to reverse geocode from coordinatest to get postcode
    try:
        time.sleep(1)
        location = GEOLOCATOR.reverse((lat, lon), addressdetails=True, timeout=10)

        if location and 'address' in location.raw:
            address = location.raw['address']
            return address.get('postcode')
        return "N/A"
    except Exception as e:
        print(f"Geocoding error at {lat}, {lon}: {e}")
        return "Error"

def as_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # convert to ESPG:4326 only for final web mapping output
    if gdf is None or len(gdf) == 0:
        return gdf
    if gdf.crs is None:
        raise ValueError("GeoDataFram no CRS value")
    if str(gdf.crs).upper() == CRS_WEB:
        return gdf
    return gdf.to_crs(CRS_WEB)

def geom_to_wgs(geom, src_crs: str):
    # convert single shapely geometry to 4326
    gs = gpd.GeoSeries([geom], crs=src_crs).to_crs(CRS_WEB)
    return gs.iloc[0]

# flood styles to show different severity levels
def rivers_style(feat):
    risk_val = feat["properties"].get("risk_val", None)
    if risk_val == 3:
        return folium_style(color="navy", weight=1.5, fill_color="navy", fill_opacity=0.35, opacity=0.9)
    if risk_val == 2:
        return folium_style(color="royalblue", weight=1.2, fill_color="royalblue", fill_opacity=0.25, opacity=0.8)
    return folium_style(color="blue", weight=1, fill_color="blue", fill_opacity=0.15, opacity=0.7)

def surface_style(feat):
    risk_val = feat["properties"].get("risk_val", None)
    if risk_val == 3:
        return folium_style(color="darkcyan", weight=1.2, fill_color="darkcyan", fill_opacity=0.35, opacity=0.9)
    if risk_val == 2:
        return folium_style(color="deepskyblue", weight=1.0, fill_color="deepskyblue", fill_opacity=0.25, opacity=0.8)
    if risk_val == 1:
        return folium_style(color="lightskyblue", weight=0.8, fill_color="lightskyblue", fill_opacity=0.18, opacity=0.7)
    return folium_style(color="deepskyblue", weight=1, fill_color="deepskyblue", fill_opacity=0.20, opacity=0.7)

def folium_style(color="black", weight=1, fill_color=None, fill_opacity=0.0, opacity=1.0):
    return {
        "color": color,
        "weight": weight,
        "opacity": opacity,
        "fillColor": fill_color if fill_color is not None else color,
        "fillOpacity": fill_opacity,
    }

def build_folium_map(
        *,
        aoi_geom,
        crs_metric: str,
        candidates_scored: gpd.GeoDataFrame,
        topN,
        lsoa: gpd.GeoDataFrame | None = None,
        parks_poly: gpd.GeoDataFrame | None = None,
        parking_poly: gpd.GeoDataFrame | None = None,
        rivers: gpd.GeoDataFrame | None = None,
        surface: gpd.GeoDataFrame | None = None,
        demand_grid_poly: gpd.GeoDataFrame | None = None,
        G_proj=None,
        walk_cutoff_m: float | None = None,
):
    
    aoi_wgs = geom_to_wgs(aoi_geom, src_crs=crs_metric)
    minx, miny, maxx, maxy = aoi_wgs.bounds
    lon_shift = (maxx - minx) * 0.15 

    center = [aoi_wgs.centroid.y, aoi_wgs.centroid.x - lon_shift]

    m = folium.Map(location=center, zoom_start=11.5, tiles=None)

    ### global styles
    style_header = """
    <style>
        .leaflet-container, .leaflet-control, .leaflet-popup-content,
        .leaflet-tooltip, .legend, .folium-map {
            font-family: sans-serif !important;
            font-size: 16px !important;
        }
        .leaflet-control-layers-overlays label,
        .leaflet-control-layers-base label {
            font-family: sans-serif !important;
            font-size: 16px !important;
        }
    </style>
    """
    m.get_root().header.add_child(folium.Element(style_header))

    folium.TileLayer(
        tiles="CartoDB positron",
        name="Basemap",
        control=True
    ).add_to(m)

    # AOI boundary
    folium.GeoJson(
        data=aoi_wgs.__geo_interface__,
        name="AOI Boundary",#
        style_function=lambda _: folium_style(color="black", weight=2, fill_opacity=0.0),
    ).add_to(m)

    # LSOA choropleth for population density
    if lsoa is not None and len(lsoa) > 0 and "pop_density" in lsoa.columns:
        lsoa_web = as_wgs84(lsoa[["pop_density", "geometry"]].copy())

        #build color scale
        vals = lsoa_web["pop_density"].replace([np.inf, -np.inf], np.nan).dropna()
        if len(vals) > 0:
            vmin, vmax = float(vals.min()), float(vals.max())
            if vmin == vmax: 
                vmax = vmin + 1.0
            cmap = linear.YlOrRd_09.scale(vmin, vmax)
            cmap.caption = "Population density"
            cmap = cmap.to_step(n=6)

            def style_fn(feat):
                v = feat["properties"].get("pop_density", None)
                if v is None:
                    return folium_style(color="black", weight=0.25, fill_opacity=0.0)
                return folium_style(
                    color="black",
                    weight=0.25,
                    fill_color=cmap(v),
                    fill_opacity=0.65,
                    opacity=0.7
                )
            folium.GeoJson(
                lsoa_web,
                name="LSOA population density",
                style_function=style_fn,
                tooltip=folium.GeoJsonTooltip(fields=["pop_density"], aliases=["Pop density:"], localize=True),
            ).add_to(m)


            cmap.add_to(m)
    

    # parks polygons
    if parks_poly is not None and len(parks_poly) > 0:
        parks_web = as_wgs84(parks_poly.copy())
        folium.GeoJson(
            parks_web,
            name="Existing parks",
            style_function=lambda _: folium_style(color="darkgreen", weight=1, fill_color="limegreen", fill_opacity=0.45),
        ).add_to(m)


    if rivers is not None and len(rivers) > 0:
        keep_cols = ["geometry", "risk_val"]
        if "risk" in rivers.columns:
            keep_cols.append("risk")
        # clip to AOI - trying to speed up lag in the output
        rivers_clip = gpd.clip(rivers, aoi_geom)[keep_cols].copy()

        # simplify in ESPG:27700 - trying to speed up output
        rivers_clip["geometry"] = rivers_clip["geometry"].simplify(tolerance=25, preserve_topology=True)
        rivers_web = as_wgs84(rivers_clip)

        tooltip_fields = ["risk_val"]
        tooltip_names = ["Severity value:"]
        if "risk" in rivers_web.columns:
            tooltip_fields = ["risk", "risk_val"]
            tooltip_names = ["Rivers/Sea class:", "Severity value:"]

        folium.GeoJson(
            rivers_web,
            name="Rivers/Sea flood risk",
            show=False,
            style_function=rivers_style,
            tooltip=folium.GeoJsonTooltip(
                fields=tooltip_fields,
                aliases=tooltip_names,
                localize=True
            ),
        ).add_to(m)

    # surface water risk
    if surface is not None and len(surface) > 0:
        keep_cols = ["geometry", "risk_val"]
        if "Risk" in surface.columns:
            keep_cols.append("Risk")

        surface_clip = gpd.clip(surface, aoi_geom)[keep_cols].copy()
        # simplify in ESPG:27700 - trying to speed up output
        surface_clip["geometry"] = surface_clip["geometry"].simplify(tolerance=25, preserve_topology=True)
        surface_web = as_wgs84(surface_clip)

        tooltip_fields = ["risk_val"]
        tooltip_names = ["Severity value:"]
        if "Risk" in surface_web.columns:
            tooltip_fields = ["Risk", "risk_val"]
            tooltip_names = ["Surface-Water class:", "Severity value:"]

        folium.GeoJson(
            surface_web,
            name="Surface-Water flood risk",
            show=False,
            style_function=surface_style,
            tooltip=folium.GeoJsonTooltip(
                fields=tooltip_fields,
                aliases=tooltip_names,
                localize=True
            ),
        ).add_to(m)

    # parking polygons
    if parking_poly is not None and len(parking_poly) > 0:
        parking_web = as_wgs84(parking_poly.copy())
        folium.GeoJson(
            parking_web,
            name="Car Parks",
            style_function=lambda _: folium_style(color="gray", weight=1, fill_color="gray", fill_opacity=0.20),
        ).add_to(m)

    ### population grid
    if demand_grid_poly is not None and len(demand_grid_poly) > 0 and "population" in demand_grid_poly.columns:
        grid_web = as_wgs84(demand_grid_poly[["population", "geometry"]].copy())

        # new population style
        def grid_style(feat):
            pop = feat["properties"].get("population", 0) or 0
            op = min(0.85, 0.05 + (float(pop) / 200.0))
            return folium_style(color="red", weight=0.2, fill_color="red", fill_opacity=op, opacity=0.6)
        folium.GeoJson(
            grid_web,
            name="100m grid population",
            style_function=grid_style,
            tooltip=folium.GeoJsonTooltip(fields=["population"], aliases=["Cell pop:"], localize=True),
        ).add_to(m)



    # top N suggested sites (markers and pop ups)
    if candidates_scored is not None and len(candidates_scored) > 0:
        top = candidates_scored.head(topN).copy()

        # representative point in original CRS (not web CRS)
        top["pt"] = top.geometry.representative_point()
        top_pts_metric = gpd.GeoDataFrame(
            top.drop(columns="geometry"),
            geometry=top["pt"],
            crs=candidates_scored.crs,
        )

        # convert the points
        top_pts_web = as_wgs84(top_pts_metric).reset_index(drop=True)

        fg_top = folium.FeatureGroup(name=f"Top {topN} suggested sites", show=True)


        for i, row in top_pts_web.iterrows():
            rank = i + 1

            # get columns but with safety (in case not there)
            score = row.get("score", None)
            flood = row.get("flood_risk_0_1", None)
            park_dist = row.get("park_dist_m", None)
            dt = row.get("demand_total_pop", None)
            du = row.get("demand_underserved_pop", None)
            area = row.get("area_m2", None)

            #flood details
            rivers_percent = row.get("rivers_flood_percent", None)
            rivers_risk = row.get("rivers_risk_0_1", None)
            surface_percent = row.get("surface_flood_percent", None)
            surface_risk = row.get("surface_risk_0_1", None)

            # Pre-format values safely
            score_s = f"{float(score):.4f}" if score is not None and score == score else "—"
            flood_s = f"{float(flood):.3f}" if flood is not None and flood == flood else "—"
            park_dist_s = f"{float(park_dist):.0f}" if park_dist is not None and park_dist == park_dist else "—"
            dt_s = f"{float(dt):,.0f}" if dt is not None and dt == dt else "—"
            du_s = f"{float(du):,.0f}" if du is not None and du == du else "—"
            area_s = f"{float(area):,.0f}" if area is not None and area == area else "—"

            # flood details
            rivers_percent_s = f"{100 * float(rivers_percent):.1f}%" if rivers_percent is not None and rivers_percent == rivers_percent else "—"
            rivers_risk_s = f"{float(rivers_risk):.3f}" if rivers_risk is not None and rivers_risk == rivers_risk else "—"
            surface_percent_s = f"{100 * float(surface_percent):.1f}%" if surface_percent is not None and surface_percent == surface_percent else "—"
            surface_risk_s = f"{float(surface_risk):.3f}" if surface_risk is not None and surface_risk == surface_risk else "—"


            popup_html = f"""
            <div style="font-family: sans-serif; font-size: 16px;">
              <b>Rank:</b> {rank}<br>
              <b>Candidate ID:</b> {row.get('cand_id', '')}<br>
              <b>Score:</b> {score_s}<br>
              <hr style="margin: 6px 0;">
              <b>Nearest-park distance (m):</b> {park_dist_s}<br>
              <b>Demand total:</b> {dt_s}<br>
              <b>Demand underserved:</b> {du_s}<br>
              <b>Area (m²):</b> {area_s}<br>
              <hr style="margin: 6px 0;">
              <b>Overall flood risk (0–1):</b> {flood_s}<br>
              <b>Rivers/Sea flood cover:</b> {rivers_percent_s}<br>
              <b>Rivers/Sea risk score:</b> {rivers_risk_s}<br>
              <b>Surface-water flood cover:</b> {surface_percent_s}<br>
              <b>Surface-water risk score:</b> {surface_risk_s}<br>
            </div>
            """


            lat, lon = row.geometry.y, row.geometry.x

            postcode_label = get_postcode(lat, lon)

            marker_html = f"""
                <div style="
                    background-color: black;
                    border: 2px solid white;
                    border-radius: 50%;
                    width: 24px;
                    height: 24px;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    color: white;
                    font-weight: bold;
                    font-size: 16px;
                    box-shadow: 0px 2px 4px rgba(0,0,0,0.3);
                ">
                    {rank}
                </div>
            """

            folium.Marker(
                location=[lat, lon],
                icon=DivIcon(
                    icon_size=(24, 24),
                    icon_anchor=(12, 12),
                    html=marker_html
                ),
                popup=folium.Popup(popup_html, max_width=360),
                tooltip=f"Rank {rank}: {postcode_label}"
            ).add_to(fg_top)

            ### testing seperate checkbox layer for each ranks wak network
            if (G_proj is not None) and (walk_cutoff_m is not None):
                cand_node = row.get("cand_node", None)
                if cand_node is not None and cand_node == cand_node:
                    cand_node = int(cand_node)

                    lengths = nx.single_source_dijkstra_path_length(
                        G_proj, cand_node, cutoff=float(walk_cutoff_m), weight="length"
                    )
                    reach_nodes = set(lengths.keys())
                    sub = G_proj.subgraph(reach_nodes)

                    lines = []
                    for u, v, data in sub.edges(data=True):
                        x1, y1 = G_proj.nodes[u]["x"], G_proj.nodes[u]["y"]
                        x2, y2 = G_proj.nodes[v]["x"], G_proj.nodes[v]["y"]
                        lines.append(LineString([(x1, y1), (x2, y2)]))

                    if len(lines) > 0:
                        gdf_lines = gpd.GeoDataFrame(
                            {"rank": [rank] * len(lines)},
                            geometry=gpd.GeoSeries(lines, crs=crs_metric),
                            crs=crs_metric
                        )

                        gdf_lines["geometry"] = gdf_lines["geometry"].simplify(
                            tolerance=5,
                            preserve_topology=True
                        )

                        lines_web = as_wgs84(gdf_lines)

                        fg_reach = folium.FeatureGroup(
                            name=f"Walk network - Rank {rank} (Score: {score_s}) - ({postcode_label})",
                            show=False
                        )

                        folium.GeoJson(
                            lines_web,
                            style_function=lambda _: folium_style(
                                color="orange",
                                weight=3,
                                opacity=0.9
                            ),
                            tooltip=f"Walk network - Rank {rank}"
                        ).add_to(fg_reach)

                        fg_reach.add_to(m)

        fg_top.add_to(m)



    
    folium.LayerControl(collapsed=False, position="topleft").add_to(m)
    return m

