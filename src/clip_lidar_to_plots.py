"""
Clips LiDAR tiles to forest inventory plot boundaries.

For each plot in the intersection table, reads the corresponding LAZ tiles,
filters points within the plot polygon, and writes a single clipped LAZ file.

Output: data/processed/03_clipped_lidar/{inventory_site}/{plot_id}.laz
"""

import logging
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import laspy
import numpy as np
import pandas as pd
from shapely import contains_xy, prepare
from shapely.geometry import Polygon
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent

def _find_lidar_dir() -> Path:
    candidates = sorted((ROOT / "data/raw/lidar").glob("LiDAR_Forest_Inventory_Brazil_*"))
    if not candidates:
        raise FileNotFoundError("Diretório LiDAR não encontrado em data/raw/lidar/. Baixe os dados do ORNL DAAC.")
    return candidates[0]

LIDAR_DIR = _find_lidar_dir()
LIDAR_CSV = LIDAR_DIR / "cms_brazil_lidar_tile_inventory.csv"
KML_DIR = ROOT / "data/processed/01_kml"
INTERSECTIONS_CSV = ROOT / "data/processed/02_intersections/lidar_inventory_intersections.csv"
OUTPUT_DIR = ROOT / "data/processed/03_clipped_lidar"


def load_inventory_plots() -> dict:
    """Returns {(site, plot_id): shapely Polygon in WGS84}"""
    plots = {}
    for kml in KML_DIR.glob("*.kml"):
        if "lidar" in kml.name:
            continue
        try:
            gdf = gpd.read_file(kml, driver="KML").set_crs("EPSG:4326")
            for _, row in gdf.iterrows():
                plots[(kml.stem, str(row["Name"]))] = row.geometry
        except Exception as e:
            log.warning(f"Could not read {kml.name}: {e}")
    return plots


def utm_proj_str(utmzone: str) -> str:
    zone_num = int(utmzone[:-1])
    south = "+south" if utmzone[-1].upper() == "S" else ""
    return f"+proj=utm +zone={zone_num} {south} +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs"


def polygon_to_utm(geometry, proj_str: str):
    gs = gpd.GeoSeries([geometry], crs="EPSG:4326")
    return gs.to_crs(proj_str).iloc[0]


def filter_points(las: laspy.LasData, polygon_utm: Polygon) -> np.ndarray:
    """Returns boolean mask of points within polygon.

    Two-pass filter: bounding box eliminates most points cheaply before
    the exact polygon test runs only on the surviving candidates.
    """
    prepare(polygon_utm)
    minx, miny, maxx, maxy = polygon_utm.bounds
    bbox_mask = (
        (las.x >= minx) & (las.x <= maxx) &
        (las.y >= miny) & (las.y <= maxy)
    )
    result = np.zeros(len(las.x), dtype=bool)
    if bbox_mask.any():
        result[bbox_mask] = contains_xy(polygon_utm, las.x[bbox_mask], las.y[bbox_mask])
    return result


def write_clipped_laz(point_chunks: list, reference_header, out_path: Path):
    """Merges point chunks (same format/scale/offset) and writes LAZ file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if len(point_chunks) == 1:
        merged = point_chunks[0]
    else:
        merged = laspy.PackedPointRecord(
            np.concatenate([chunk.array for chunk in point_chunks]),
            point_chunks[0].point_format,
        )

    # laspy only writes LAS >= 1.2; upgrade silently if source is older
    version = reference_header.version
    if (version.major, version.minor) < (1, 2):
        version = "1.2"

    new_las = laspy.LasData(header=laspy.LasHeader(
        version=version,
        point_format=reference_header.point_format,
    ))
    new_las.header.scales = reference_header.scales
    new_las.header.offsets = reference_header.offsets
    new_las.points = merged
    new_las.write(out_path)


def main():
    intersections = pd.read_csv(INTERSECTIONS_CSV)
    lidar_meta = pd.read_csv(LIDAR_CSV).set_index("filename")

    log.info("Loading inventory plot polygons...")
    plots = load_inventory_plots()
    log.info(f"  {len(plots)} plots loaded")

    # Build: {laz_file: [(site, plot_id), ...]}
    by_laz: dict[str, list] = defaultdict(list)
    for _, row in intersections.iterrows():
        by_laz[row.laz_file].append((row.inventory_file, str(row.plot_id)))

    # Accumulate: {(site, plot_id): (list of point chunks, reference header)}
    plot_chunks: dict[tuple, list] = defaultdict(list)
    plot_header: dict[tuple, laspy.LasHeader] = {}

    log.info(f"Reading {len(by_laz)} LAZ tiles...")
    for laz_file, plot_keys in tqdm(by_laz.items(), unit="tile"):
        laz_path = LIDAR_DIR / laz_file
        if not laz_path.exists():
            log.warning(f"Missing: {laz_file}")
            continue

        utmzone = lidar_meta.loc[laz_file, "utmzone"]
        proj_str = utm_proj_str(utmzone)

        try:
            las = laspy.read(laz_path)
        except Exception as e:
            log.warning(f"Skipping corrupt tile {laz_file}: {e}")
            continue

        for site, plot_id in plot_keys:
            key = (site, plot_id)
            polygon_wgs84 = plots.get(key)
            if polygon_wgs84 is None:
                continue

            polygon_utm = polygon_to_utm(polygon_wgs84, proj_str)
            mask = filter_points(las, polygon_utm)
            if mask.sum() == 0:
                continue

            plot_chunks[key].append(las.points[mask])
            if key not in plot_header:
                plot_header[key] = las.header

    log.info(f"\nWriting {len(plot_chunks)} clipped LAZ files...")
    written, empty = 0, 0
    for key, chunks in tqdm(plot_chunks.items(), unit="plot"):
        site, plot_id = key
        out_path = OUTPUT_DIR / site / f"plot_{plot_id}.laz"
        write_clipped_laz(chunks, plot_header[key], out_path)
        written += 1

    no_points = set(
        (row.inventory_file, str(row.plot_id))
        for _, row in intersections.iterrows()
    ) - set(plot_chunks.keys())
    empty = len(no_points)

    log.info(f"\nDone.")
    log.info(f"  Written: {written} LAZ files")
    log.info(f"  Empty (no points after clip): {empty} plots")
    log.info(f"  Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
