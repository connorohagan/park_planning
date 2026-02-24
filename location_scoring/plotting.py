# plotting.py

import geopandas as gpd

def draw_map(ax, *, aoi_geom, edges, lsoa, parks_poly, parking_poly, removed, parking_point, rivers, surface, candidates_scored, purples_dark, crs_metric, 
             zoom_bounds=None, is_zoomed=False, topN=10, title_full="Full View", title_zoom="Detailed View"):

    # flood layers
    if len(rivers) > 0:
        rivers.sort_values("risk_val").plot(ax=ax, 
                                            column="risk_val", 
                                            cmap="Blues",
                                            alpha=0.8, 
                                            linewidth=0, 
                                            edgecolor="none", 
                                            legend=False)
    if len(surface) > 0:
        surface.sort_values("risk_val").plot(ax=ax, 
                                             column="risk_val", 
                                             cmap=purples_dark,
                                             alpha=0.8, 
                                             linewidth=0.2, 
                                             edgecolor="purple", 
                                             legend=False)

    # population density
    lsoa.plot(ax=ax, column="pop_density", cmap="YlOrRd", legend=False, alpha=0.75, linewidth=0.0)

    # walk network
    edges.plot(ax=ax, linewidth=0.35, alpha=0.6, color="black")

    # parks
    if len(parks_poly) > 0:
        parks_poly.plot(ax=ax, alpha=0.75, color="limegreen", edgecolor="darkgreen", linewidth=0.5)

    # parking polys
    if len(parking_poly) > 0:
        parking_poly.plot(ax=ax, alpha=0.55, color="none", edgecolor="fuchsia", hatch="////", linewidth=1.0)

    removed.plot(ax=ax, color="red", edgecolor="darkred", alpha=0.8, linewidth=0.5)

    # top candidates points and label
    top = candidates_scored.head(topN).copy()
    top["pt"] = top.geometry.representative_point()

    gpd.GeoSeries(top["pt"], crs=top.crs).plot(
        ax=ax, color="cyan", markersize=120, alpha=0.95, edgecolor="black", linewidth=1.2, zorder=55
    )
    top = top.reset_index(drop=True)
    for i, row in top.iterrows():
        ax.annotate(
            str(i+1),
            xy=(row["pt"].x, row["pt"].y),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=12,
            fontweight="bold",
            zorder=60
        )

    # parking points
    if len(parking_point) > 0:
        parking_point.plot(ax=ax, markersize=10, alpha=0.85, color="gold", edgecolor="black", linewidth=0.6)

    # AOI boundary
    gpd.GeoSeries([aoi_geom], crs=crs_metric).boundary.plot(ax=ax, linewidth=2.0, color="black")

    if is_zoomed and zoom_bounds is not None:
        ax.set_xlim(zoom_bounds[0], zoom_bounds[1])
        ax.set_ylim(zoom_bounds[2], zoom_bounds[3])
        ax.set_title(title_zoom, fontsize=20, pad=20)
    else:
        b = aoi_geom.bounds
        ax.set_xlim(b[0], b[2])
        ax.set_ylim(b[1], b[3])
        ax.set_title(title_full, fontsize=20, pad=20)

    ax.axis("off")