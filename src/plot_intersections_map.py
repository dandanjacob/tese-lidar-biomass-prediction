"""
Generates a map of Brazil showing all inventory plots that have LiDAR coverage.
Output: data/processed/02_intersections/map_intersections.png
"""

from pathlib import Path

import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
from geodatasets import get_path

ROOT = Path(__file__).parent.parent
KML_DIR = ROOT / "data/processed/01_kml"
INTERSECTIONS_CSV = ROOT / "data/processed/02_intersections/lidar_inventory_intersections.csv"
LIDAR_CSV = ROOT / "data/raw/lidar/LiDAR_Forest_Inventory_Brazil_1644_1-20260505_011031/cms_brazil_lidar_tile_inventory.csv"
OUTPUT = ROOT / "data/processed/02_intersections/map_intersections.png"


def load_brazil():
    from shapely.geometry import box
    land = gpd.read_file(get_path("naturalearth.land"))
    brazil_bbox = box(-74, -34, -28, 6)
    brazil = land.clip(brazil_bbox)
    return brazil


def load_all_inventory_plots():
    kmls = [p for p in KML_DIR.glob("*.kml") if "lidar" not in p.name]
    frames = []
    for kml in kmls:
        try:
            gdf = gpd.read_file(kml, driver="KML").set_crs("EPSG:4326")
            gdf["site"] = kml.stem
            gdf["plot_id"] = gdf["Name"].astype(str)
            frames.append(gdf[["site", "plot_id", "geometry"]])
        except Exception:
            pass
    return pd.concat(frames, ignore_index=True) if frames else gpd.GeoDataFrame()


def load_lidar_tiles_used(intersections):
    lidar_meta = pd.read_csv(LIDAR_CSV)
    used = lidar_meta[lidar_meta["filename"].isin(intersections["laz_file"])]
    from shapely.geometry import box
    geoms = [box(r.min_lon, r.min_lat, r.max_lon, r.max_lat) for r in used.itertuples()]
    return gpd.GeoDataFrame(used[["filename"]], geometry=geoms, crs="EPSG:4326")


def main():
    print("Carregando dados...")
    intersections = pd.read_csv(INTERSECTIONS_CSV)
    intersected_keys = set(zip(intersections["inventory_file"], intersections["plot_id"].astype(str)))

    brazil = load_brazil()
    all_plots = load_all_inventory_plots()
    lidar_tiles = load_lidar_tiles_used(intersections)

    all_plots["has_lidar"] = all_plots.apply(
        lambda r: (r["site"], r["plot_id"]) in intersected_keys, axis=1
    )

    with_lidar = all_plots[all_plots["has_lidar"]]
    without_lidar = all_plots[~all_plots["has_lidar"]]

    unique_with = len(intersected_keys)
    unique_without = len(all_plots.groupby(["site", "plot_id"])) - unique_with

    print(f"  Parcelas únicas com LiDAR: {unique_with}")
    print(f"  Parcelas únicas sem LiDAR: {unique_without}")
    print(f"  Tiles LiDAR usados: {len(lidar_tiles)}")

    fig, ax = plt.subplots(figsize=(14, 14))

    brazil.plot(ax=ax, color="#e8f4e8", edgecolor="#555555", linewidth=1.2, zorder=1)

    lidar_tiles.plot(
        ax=ax, color="#a8d5f5", alpha=0.25, edgecolor="#4a90d9",
        linewidth=0.3, zorder=2, label="Tiles LiDAR"
    )

    without_lidar.plot(
        ax=ax, color="#cccccc", markersize=18, zorder=3, alpha=0.7
    )

    with_lidar.plot(
        ax=ax, color="#e84545", markersize=35, zorder=4,
        edgecolor="white", linewidth=0.5
    )

    # Annotate site names for intersected plots
    site_centroids = with_lidar.copy()
    site_centroids["lon"] = site_centroids.geometry.centroid.x
    site_centroids["lat"] = site_centroids.geometry.centroid.y
    labeled = site_centroids.groupby("site")[["lon", "lat"]].mean().reset_index()
    labeled["label"] = labeled["site"].str.extract(r"^([A-Z]+_A\d+)")[0]

    for _, row in labeled.iterrows():
        ax.annotate(
            row["label"],
            xy=(row["lon"], row["lat"]),
            xytext=(6, 6), textcoords="offset points",
            fontsize=6.5, color="#222222",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.6, ec="none"),
        )

    # Legend
    legend_handles = [
        mpatches.Patch(color="#a8d5f5", alpha=0.6, label=f"Tiles LiDAR usados ({len(lidar_tiles)})"),
        mpatches.Patch(color="#e84545", label=f"Parcelas com LiDAR ({unique_with} únicas)"),
        mpatches.Patch(color="#cccccc", label=f"Parcelas sem LiDAR ({unique_without} únicas)"),
    ]
    ax.legend(handles=legend_handles, loc="lower left", fontsize=10, framealpha=0.9)

    ax.set_xlim(-75, -34)
    ax.set_ylim(-34, 6)
    ax.set_title(
        "Parcelas de inventário florestal × cobertura LiDAR\nAmazônia Brasileira",
        fontsize=15, fontweight="bold", pad=16
    )
    ax.set_xlabel("Longitude", fontsize=10)
    ax.set_ylabel("Latitude", fontsize=10)
    ax.grid(True, alpha=0.3, linestyle="--")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, dpi=180, bbox_inches="tight")
    print(f"\nMapa salvo em: {OUTPUT}")


if __name__ == "__main__":
    main()
