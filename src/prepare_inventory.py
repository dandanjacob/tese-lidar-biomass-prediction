"""
Prepares inventory CSVs for analysis.

For each site with LiDAR intersections:
  1. Loads raw CSV (handles encoding latin-1, separators , and ;)
  2. Normalizes column names to a consistent schema
  3. Assigns plot_id to each tree via point-in-polygon using tree UTM
     coordinates and KML plot polygons (robust to naming inconsistencies)
  4. Filters to only plots present in the intersection table
  5. Adds htot_feldpausch — height estimated from DBH via Weibull H-D model
     (Feldpausch et al. 2012, Table 3, E. C. Amazonia region)
     Original htot_{year} columns are preserved unchanged.
  6. Saves to data/processed/04_inventory/{site}.csv in UTF-8

Output columns always present (when source has the data):
  site, plot_id, tree_id, scientific_name, family_name,
  dbh_{year}, htot_{year}, hcom_{year}, type_{year}, dead_{year}, wsd,
  htot_feldpausch  ← estimated height (m); populated for all trees with DBH

  type: O = tree, P = palm
  dead: True/False
  wsd:  wood specific density (only pre-computed in FST_A01)

Height estimation (Feldpausch et al. 2012, Biogeosciences 9:3381-3403, Table 3):
  Region:  Eastern-Central Amazonia  (default for all sites in this project)
  Model:   H = a * (1 - exp(-b * D^c))
  Params:  a=48.131, b=0.0375, c=0.8228, RSE=4.918
  Bias correction: C_F = exp(RSE^2 / 2) applied to the estimate
"""

import re
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
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


def _norm_col(s: str) -> str:
    """Chave de coluna robusta a separadores: 'UTM Easting', 'UTM.Easting',
    'UTM_Easting' e 'UTMEasting' colapsam todas para 'utmeasting'."""
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def normalize_columns(raw: pd.DataFrame) -> pd.DataFrame:
    # Lookup das colunas do raw por chave normalizada (1ª ocorrência vence).
    by_norm: dict[str, str] = {}
    for c in raw.columns:
        by_norm.setdefault(_norm_col(c), c)

    out = pd.DataFrame()
    for out_name, candidates in SCALAR_MAP:
        for cand in candidates:
            rc = by_norm.get(_norm_col(cand))
            if rc is not None:
                out[out_name] = raw[rc]
                break
    for out_name, candidates in BARE_MAP.items():
        for cand in candidates:
            rc = by_norm.get(_norm_col(cand))
            if rc is not None and out_name not in out.columns:
                out[out_name] = raw[rc]
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

def _ensure_polygon(geom):
    """(Multi)LineString de anel fechado → polígono. Vários KMLs (FNA, TAP_A0x) trazem
    as parcelas como LINHAS, não polígonos; sem isso o point-in-polygon nunca acerta
    (um ponto nunca está 'within' uma linha). Espelha app/lib/data.py:_ensure_polygon."""
    from shapely.ops import polygonize, unary_union
    if geom is None or geom.is_empty:
        return geom
    if geom.geom_type in ("LineString", "MultiLineString"):
        polys = list(polygonize(geom))
        if polys:
            return unary_union(polys)
    return geom


def load_kml_plots(site_key: str) -> gpd.GeoDataFrame | None:
    """Loads KML plot polygons for a site, returns GeoDataFrame or None."""
    kml = KML_DIR / f"{site_key}.kml"
    if not kml.exists():
        return None
    try:
        gdf = gpd.read_file(kml, driver="KML").set_crs("EPSG:4326")
        gdf["geometry"] = gdf.geometry.apply(_ensure_polygon)
        gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
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
        # Coordenadas em graus. Alguns sites (ex. DUC_A01_2016) trazem lat/lon
        # TROCADOS (easting=latitude, northing=longitude). Testa as duas ordens e
        # fica com a que coloca mais árvores dentro das parcelas.
        kml_union = kml_plots.geometry.union_all()

        def _pts(lon_col, lat_col):
            pts = [Point(lo, la) for lo, la in zip(trees[lon_col], trees[lat_col])]
            hits = sum(kml_union.contains(p) for p in pts[:300])
            return hits, pts

        hit_ne, pts_ne = _pts("utm_easting", "utm_northing")   # easting=lon, northing=lat
        hit_sw, pts_sw = _pts("utm_northing", "utm_easting")   # trocado
        geom = pts_sw if hit_sw > hit_ne else pts_ne
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


# ── Feldpausch 2012 height estimation ────────────────────────────────────────
# Table 3 — E. C. Amazonia (default region for this project)
# Feldpausch 2012 Table 3 — Eastern-Central Amazonia
# H = a * (1 - exp(-b * D^c))   [D in cm, H in m]
# C_F (Eq. 6) applies to log-linear biomass models, NOT to this Weibull — omitted here.
_FELD_A, _FELD_B, _FELD_C = 48.131, 0.0375, 0.8228


def estimate_height_feldpausch(dbh_series: pd.Series) -> pd.Series:
    """Estimates tree height (m) from DBH (cm) using Feldpausch et al. 2012.

    H = a * (1 - exp(-b * D^c))
    Region: Eastern-Central Amazonia  (a=48.131, b=0.0375, c=0.8228, RSE=4.918)
    Returns NaN for rows where DBH is missing or non-positive.
    """
    dbh = pd.to_numeric(dbh_series, errors="coerce")
    valid = dbh > 0
    h = pd.Series(np.nan, index=dbh.index)
    h[valid] = _FELD_A * (1 - np.exp(-_FELD_B * dbh[valid] ** _FELD_C))
    return h.round(2)


def add_estimated_height(df: pd.DataFrame) -> pd.DataFrame:
    """Adds htot_feldpausch column using the best available DBH column."""
    dbh_cols = sorted([c for c in df.columns if c.startswith("dbh_")],
                      key=lambda c: c.split("_")[-1], reverse=True)
    bare_dbh = "dbh" if "dbh" in df.columns else None
    src = dbh_cols[0] if dbh_cols else bare_dbh
    if src is None:
        df["htot_feldpausch"] = np.nan
    else:
        df["htot_feldpausch"] = estimate_height_feldpausch(df[src])
    return df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    intersections = pd.read_csv(INTER_CSV)
    valid_plots: dict[str, set] = {}
    for _, row in intersections.iterrows():
        key = row["inventory_file"]
        pid = str(row["plot_id"]).strip()
        # A interseção usa o plot_id CORRIGIDO (ex. "T01_1"/"T01_2" em sites
        # multiparte), mas a atribuição espacial devolve o Name cru do KML ("T01").
        # Aceita ambos: o nome-base (campo) e o corrigido — senão sites multiparte
        # (CAU, PAR, TAN, FST) caem para zero árvores. A separação em quadras é feita
        # depois, em calculate_biomass.
        valid_plots.setdefault(key, set()).add(pid)
        valid_plots[key].add(re.sub(r"_\d+$", "", pid))

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

        df = add_estimated_height(df)

        out_path = OUT_DIR / f"{site_key}.csv"
        df.to_csv(out_path, index=False, encoding="utf-8")

    log.info(f"\nConcluído: {sites_done} sites, {sites_warn} warnings, {sites_err} erros")
    log.info(f"Total de árvores: {total_trees:,}")
    log.info(f"Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
