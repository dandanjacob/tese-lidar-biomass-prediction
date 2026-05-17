"""
Generates an interactive HTML map of all inventory plots and LiDAR tiles.
Output: data/processed/02_intersections/map_intersections.html
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

ROOT = Path(__file__).parent.parent
KML_DIR = ROOT / "data/processed/01_kml"
INTERSECTIONS_CSV = ROOT / "data/processed/02_intersections/lidar_inventory_intersections.csv"
LIDAR_CSV = ROOT / "data/raw/lidar/LiDAR_Forest_Inventory_Brazil_1644_1-20260505_011031/cms_brazil_lidar_tile_inventory.csv"
OUTPUT = ROOT / "data/processed/02_intersections/map_intersections.html"


def load_inventory_plots(intersected_keys):
    kmls = [p for p in KML_DIR.glob("*.kml") if "lidar" not in p.name]
    frames = []
    for kml in kmls:
        try:
            gdf = gpd.read_file(kml, driver="KML").set_crs("EPSG:4326")
            gdf["site"] = kml.stem
            gdf["plot_id"] = gdf["Name"].astype(str)
            gdf["has_lidar"] = gdf.apply(
                lambda r: (r["site"], r["plot_id"]) in intersected_keys, axis=1
            )
            gdf["label"] = gdf["site"].str.extract(r"^([A-Z]+_A\d+)")[0] + " / " + gdf["plot_id"]
            frames.append(gdf[["site", "plot_id", "label", "has_lidar", "geometry"]])
        except Exception as e:
            print(f"  Aviso: {kml.name}: {e}")
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")


def load_lidar_tiles(intersected_laz_files):
    meta = pd.read_csv(LIDAR_CSV)
    used = meta[meta["filename"].isin(intersected_laz_files)].copy()
    used["geometry"] = [
        box(r.min_lon, r.min_lat, r.max_lon, r.max_lat) for r in used.itertuples()
    ]
    return gpd.GeoDataFrame(used[["filename", "utmzone", "geometry"]], crs="EPSG:4326")


def main():
    print("Carregando dados...")
    intersections = pd.read_csv(INTERSECTIONS_CSV)
    intersected_keys = set(zip(intersections["inventory_file"], intersections["plot_id"].astype(str)))
    intersected_laz = set(intersections["laz_file"])

    plots = load_inventory_plots(intersected_keys)
    tiles = load_lidar_tiles(intersected_laz)

    with_lidar = plots[plots["has_lidar"]].copy()
    without_lidar = plots[~plots["has_lidar"]].copy()

    print(f"  Parcelas com LiDAR: {len(intersected_keys)} únicas ({len(with_lidar)} polígonos)")
    print(f"  Parcelas sem LiDAR: {len(without_lidar)} polígonos")
    print(f"  Tiles LiDAR: {len(tiles)}")

    # Base map centered on Amazon
    center = [-5.5, -57.0]

    m = tiles.explore(
        tooltip=["filename", "utmzone"],
        color="#4a90d9",
        style_kwds={"fillOpacity": 0.15, "weight": 0.8, "color": "#4a90d9"},
        name="Tiles LiDAR (252)",
        location=center,
        zoom_start=5,
        tiles="CartoDB positron",
    )

    without_lidar.explore(
        m=m,
        tooltip=["label", "site", "plot_id"],
        color="#aaaaaa",
        style_kwds={"fillOpacity": 0.5, "weight": 1.2, "color": "#888888"},
        name=f"Parcelas sem LiDAR (79)",
    )

    with_lidar.explore(
        m=m,
        tooltip=["label", "site", "plot_id"],
        color="#e84545",
        style_kwds={"fillOpacity": 0.65, "weight": 1.5, "color": "#c0392b"},
        name=f"Parcelas com LiDAR (294)",
    )

    import folium
    folium.LayerControl(collapsed=False).add_to(m)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    m.save(OUTPUT)
    print(f"\nMapa salvo em: {OUTPUT}")


if __name__ == "__main__":
    main()
