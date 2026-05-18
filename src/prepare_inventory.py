"""
Prepares inventory CSVs for analysis.

For each site with LiDAR intersections:
  1. Loads raw CSV (handles encoding latin-1, separators , and ;)
  2. Normalizes column names to a consistent schema
  3. Assigns plot_id to each tree via point-in-polygon using tree UTM
     coordinates and KML plot polygons (robust to naming inconsistencies)
  4. Filters to only plots present in the intersection table
  5. Saves to data/processed/04_inventory/{site}.csv in UTF-8

Output columns always present (when source has the data):
  site, plot_id, tree_id, scientific_name, family_name,
  dbh_{year}, htot_{year}, hcom_{year}, type_{year}, dead_{year}, wsd

  type: O = tree, P = palm
  dead: True/False
  wsd:  wood specific density (only pre-computed in FST_A01)
"""

import re
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

ROOT      = Path(__file__).parent.parent
INV_DIR   = ROOT / "data/raw/inventory/Forest_Inventory_Brazil_2007_1-20260505_010726"
KML_DIR   = ROOT / "data/processed/01_kml"
INTER_CSV = ROOT / "data/processed/02_intersections/lidar_inventory_intersections.csv"
OUT_DIR   = ROOT / "data/processed/04_inventory"


# ── Column normalization ───────────────────────────────────────────────────────

SCALAR_MAP = [
    ("site",            ["area", "Area"]),
    ("tree_id",         ["tree"]),
    ("scientific_name", ["scientific.name", "scientific_name", "scienfic_name", "scienfic_name "]),
    ("family_name",     ["family.name", "family_name"]),
    ("utm_easting",     ["UTM.Easting", "UTM_Easting"]),
    ("utm_northing",    ["UTM.Northing", "UTM_Northing"]),
    ("wsd",             ["WSD", "wsd"]),
    ("agb_source",      ["AGB"]),
]

YEAR_PATTERNS = {
    "dbh":  re.compile(r"^DBH[._]?(\d{2,4})$", re.I),
    "htot": re.compile(r"^Htot[._]?(\d{2,4})$", re.I),
    "hcom": re.compile(r"^Hcom[._]?(\d{2,4})$", re.I),
    "dead": re.compile(r"^Dead[._]?(\d{2,4})$", re.I),
    "type": re.compile(r"^type[._]?(\d{2,4})$", re.I),
}

BARE_MAP = {
    "dbh":  ["DBH"],
    "htot": ["Htot", "htot"],
    "hcom": ["Hcom", "hcom"],
    "dead": ["Dead", "dead"],
    "type": ["type"],
}


def detect_sep(path: Path) -> str:
    sample = path.read_bytes()[:2000].decode("latin-1", errors="replace")
    return ";" if sample.count(";") > sample.count(",") else ","


def normalize_year(s: str) -> str:
    s = s.strip()
    return f"20{s}" if len(s) == 2 else s


def normalize_columns(raw: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    for out_name, candidates in SCALAR_MAP:
        for cand in candidates:
            if cand in raw.columns:
                out[out_name] = raw[cand]
                break
    for out_name, candidates in BARE_MAP.items():
        for cand in candidates:
            if cand in raw.columns and out_name not in out.columns:
                out[out_name] = raw[cand]
                break
    for col in raw.columns:
        for prefix, pattern in YEAR_PATTERNS.items():
            m = pattern.match(col)
            if m:
                year = normalize_year(m.group(1))
                out_col = f"{prefix}_{year}"
                if out_col not in out.columns:
                    out[out_col] = raw[col]
    return out


# ── Plot assignment via point-in-polygon ──────────────────────────────────────

def load_kml_plots(site_key: str) -> gpd.GeoDataFrame | None:
    """Loads KML plot polygons for a site, returns GeoDataFrame or None."""
    kml = KML_DIR / f"{site_key}.kml"
    if not kml.exists():
        return None
    try:
        gdf = gpd.read_file(kml, driver="KML").set_crs("EPSG:4326")
        gdf["plot_id"] = gdf["Name"].astype(str).str.strip()
        return gdf[["plot_id", "geometry"]]
    except Exception as e:
        log.warning(f"  Não foi possível ler KML {kml.name}: {e}")
        return None


def assign_plots_spatial(df: pd.DataFrame, kml_plots: gpd.GeoDataFrame,
                         valid_plot_ids: set) -> pd.DataFrame:
    """
    Assigns plot_id to each tree using point-in-polygon with tree UTM coords.
    Filters to valid_plot_ids. Returns df with plot_id column added.
    """
    if "utm_easting" not in df.columns or "utm_northing" not in df.columns:
        return df

    trees = df.copy()
    trees["utm_easting"]  = pd.to_numeric(trees["utm_easting"],  errors="coerce")
    trees["utm_northing"] = pd.to_numeric(trees["utm_northing"], errors="coerce")
    trees = trees.dropna(subset=["utm_easting", "utm_northing"])
    if trees.empty:
        return df

    easting_mean = trees["utm_easting"].mean()

    # Detect coordinate system: lat/lon (|easting| < 180) vs UTM (easting > 1000)
    if abs(easting_mean) < 180:
        # Coordinates are lon/lat — build GeoDataFrame directly in WGS84
        geom = [Point(e, n) for e, n in zip(trees["utm_easting"], trees["utm_northing"])]
        trees_gdf = gpd.GeoDataFrame(trees.copy(), geometry=geom, crs="EPSG:4326")
        kml_utm = kml_plots  # already WGS84
    else:
        # Coordinates are UTM — reproject KML to matching UTM zone
        kml_centroid = kml_plots.geometry.union_all().centroid
        lon, lat = kml_centroid.x, kml_centroid.y
        zone = int((lon + 180) / 6) + 1
        hemi = "south" if lat < 0 else ""
        proj_str = f"+proj=utm +zone={zone} +{hemi} +ellps=WGS84 +units=m +no_defs"
        kml_utm = kml_plots.to_crs(proj_str)
        geom = [Point(e, n) for e, n in zip(trees["utm_easting"], trees["utm_northing"])]
        trees_gdf = gpd.GeoDataFrame(trees.copy(), geometry=geom, crs=proj_str)

    joined = gpd.sjoin(trees_gdf, kml_utm[["plot_id", "geometry"]],
                       how="left", predicate="within")
    # drop duplicates from overlapping polygons — keep first match per tree
    joined = joined[~joined.index.duplicated(keep="first")]
    pid_col = "plot_id_right" if "plot_id_right" in joined.columns else "plot_id"
    assigned = joined[pid_col].reindex(trees_gdf.index)

    df = df.copy()
    df["plot_id"] = pd.NA
    df.loc[trees.index, "plot_id"] = assigned.values

    return df[df["plot_id"].isin(valid_plot_ids)].copy()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    intersections = pd.read_csv(INTER_CSV)
    valid_plots: dict[str, set] = {}
    for _, row in intersections.iterrows():
        key = row["inventory_file"]
        valid_plots.setdefault(key, set()).add(str(row["plot_id"]).strip())

    total_trees = 0
    sites_done, sites_warn, sites_err = 0, 0, 0

    for site_key, plot_ids in sorted(valid_plots.items()):
        base = site_key.replace("_inventory_plots", "").replace("_inventory", "")
        candidates = (list(INV_DIR.glob(f"{base}*Inventory*.csv")) +
                      list(INV_DIR.glob(f"{base}*inventory*.csv")))
        if not candidates:
            log.warning(f"  [SKIP] CSV não encontrado: {site_key}")
            sites_err += 1
            continue

        try:
            raw = pd.read_csv(candidates[0], encoding="latin-1",
                              sep=detect_sep(candidates[0]), low_memory=False)
        except Exception as e:
            log.error(f"  [ERR]  {candidates[0].name}: {e}")
            sites_err += 1
            continue

        df = normalize_columns(raw)

        # Assign plot_id via spatial join (handles naming inconsistencies)
        kml_plots = load_kml_plots(site_key)
        if kml_plots is not None:
            df = assign_plots_spatial(df, kml_plots, plot_ids)
        else:
            # Fallback: try matching existing plot column
            if "plot_id" in df.columns:
                df["plot_id"] = df["plot_id"].astype(str).str.strip()
                df = df[df["plot_id"].isin(plot_ids)].copy()

        if df.empty:
            log.warning(f"  [WARN] Zero árvores após filtro: {site_key}")
            sites_warn += 1
        else:
            log.info(f"  [OK]   {site_key:<50}  {len(df):>5} árvores")
            total_trees += len(df)
            sites_done += 1

        out_path = OUT_DIR / f"{site_key}.csv"
        df.to_csv(out_path, index=False, encoding="utf-8")

    log.info(f"\nConcluído: {sites_done} sites, {sites_warn} warnings, {sites_err} erros")
    log.info(f"Total de árvores: {total_trees:,}")
    log.info(f"Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
