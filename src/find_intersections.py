"""
Finds which LiDAR tiles intersect each forest inventory plot.
Outputs: data/processed/02_intersections/lidar_inventory_intersections.csv
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

ROOT = Path(__file__).parent.parent

def _find_lidar_dir() -> Path:
    candidates = sorted((ROOT / "data/raw/lidar").glob("LiDAR_Forest_Inventory_Brazil_*"))
    if not candidates:
        raise FileNotFoundError("Diretório LiDAR não encontrado em data/raw/lidar/. Baixe os dados do ORNL DAAC.")
    return candidates[0]

LIDAR_CSV = _find_lidar_dir() / "cms_brazil_lidar_tile_inventory.csv"
KML_DIR = ROOT / "data/processed/01_kml"
OUTPUT = ROOT / "data/processed/02_intersections/lidar_inventory_intersections.csv"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def load_lidar_tiles() -> gpd.GeoDataFrame:
    df = pd.read_csv(LIDAR_CSV)
    geometries = [
        box(row.min_lon, row.min_lat, row.max_lon, row.max_lat)
        for row in df.itertuples()
    ]
    return gpd.GeoDataFrame(df[["filename"]], geometry=geometries, crs="EPSG:4326")


def load_inventory_plots() -> gpd.GeoDataFrame:
    kmls = [p for p in KML_DIR.glob("*.kml") if "lidar" not in p.name]
    frames = []
    for kml in kmls:
        try:
            gdf = gpd.read_file(kml, driver="KML")
            gdf["inventory_file"] = kml.stem
            frames.append(gdf[["Name", "inventory_file", "geometry"]])
        except Exception as e:
            print(f"  Aviso: não foi possível ler {kml.name}: {e}")
    return pd.concat(frames, ignore_index=True)


def main():
    print("Carregando tiles LiDAR...")
    lidar = load_lidar_tiles()
    print(f"  {len(lidar)} tiles")

    print("Carregando plots de inventário...")
    inventory = load_inventory_plots()
    inventory = inventory.set_crs("EPSG:4326")
    print(f"  {len(inventory)} plots")

    print("Calculando interseções...")
    joined = gpd.sjoin(inventory, lidar, how="inner", predicate="intersects")

    result = (
        joined[["inventory_file", "Name", "filename"]]
        .rename(columns={"Name": "plot_id", "filename": "laz_file"})
        .sort_values(["inventory_file", "plot_id"])
        .reset_index(drop=True)
    )

    result.to_csv(OUTPUT, index=False)

    print(f"\nResultado salvo em: {OUTPUT}")
    print(f"Total de pares (plot x tile): {len(result)}")
    print(f"Plots com cobertura LiDAR: {result['plot_id'].nunique()}")
    print(f"Sites de inventário cobertos: {result['inventory_file'].nunique()}")
    print(f"Tiles LiDAR utilizados: {result['laz_file'].nunique()}")
    print("\nPrimeiras linhas:")
    print(result.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
