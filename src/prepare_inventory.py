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
  6. Adds htot_estimated / htot_estimation_method — prefers a height model
     fit locally per site (log Htot ~ log DBH [+ log Hcom]) when the site
     has enough paired measurements, else falls back to htot_feldpausch.
     See fit_local_height_model() for rationale.
  7. Saves to data/processed/04_inventory/{site}.csv in UTF-8

Output columns always present (when source has the data):
  site, plot_id, tree_id, scientific_name, family_name,
  dbh_{year}, htot_{year}, hcom_{year}, date_{year}, type_{year}, dead_{year}, wsd,
  htot_feldpausch        ← regional estimate (m); populated for all trees with DBH
  htot_estimated         ← measured > local site fit > regional fallback
  htot_estimation_method ← "measured" | "local_fit" | "feldpausch_regional"

  type: O = tree, P = palm
  dead: True/False
  wsd:  wood specific density (only pre-computed in FST_A01)
  date_{year}: measurement date (YYYYMMDD) for that campaign, when recorded

Height estimation (Feldpausch et al. 2012, Biogeosciences 9:3381-3403, Table 3):
  Region:  Eastern-Central Amazonia  (default for all sites in this project)
  Model:   H = a * (1 - exp(-b * D^c))
  Params:  a=48.131, b=0.0375, c=0.8228, RSE=4.918
  Bias correction: C_F = exp(RSE^2 / 2) applied to the estimate

Local per-site height model (htot_estimated, when enough data):
  log(Htot) = b0 + b1*log(DBH) [+ b2*log(Hcom)], fit by OLS on that site's
  own measured trees, with a Baskerville/Sprugel back-transform bias
  correction C_F = exp(sigma^2 / 2) applied. Each site is a different
  region/forest type, so a locally-fit curve captures site-specific
  height-diameter allometry that one pan-Amazonian regional curve can't.
  Requires >= MIN_LOCAL_FIT_N paired Htot/DBH measurements; most sites in
  this dataset have zero measured heights and always fall back to the
  regional Feldpausch curve.
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
TEMP_CSV  = ROOT / "data/processed/02_intersections/intersections_temporal.csv"
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
    "date": re.compile(r"^date[._]?(\d{2,4})$", re.I),
    "dead": re.compile(r"^Dead[._]?(\d{2,4})$", re.I),
    "type": re.compile(r"^type[._]?(\d{2,4})$", re.I),
}

BARE_MAP = {
    "dbh":  ["DBH"],
    "htot": ["Htot", "htot"],
    "hcom": ["Hcom", "hcom"],
    "date": ["date", "Date"],
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


# Largura do corredor (meia-largura, em metros) usada para transformar linhas de
# transecto em polígono. Alguns sites (TAP_A01_2009, TAP_A04, TAP_A05) trazem as
# parcelas como LINHAS DE TRANSECTO abertas (~500m), não anéis fechados: polygonize
# devolve vazio. As árvores ficam a ≤20m da sua linha e o transecto vizinho está a
# ≥200m, então um buffer de 50m captura todas as árvores sem sobreposição entre
# transectos. Medido empiricamente nos três sites.
TRANSECT_BUFFER_M = 50.0


def _buffer_lines_to_corridors(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Linhas de transecto abertas → polígono-corredor (buffer em UTM local).

    Opera só nas linhas que sobraram após _ensure_polygon (anéis genuínos já viraram
    polígono via polygonize). Buffer feito em metros reprojetando para a zona UTM do
    centroide e voltando para WGS84, preservando a interface (GeoDataFrame em 4326)."""
    is_line = gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])
    if not is_line.any():
        return gdf
    cen = gdf.geometry.union_all().centroid
    zone = int((cen.x + 180) / 6) + 1
    hemi = "south" if cen.y < 0 else ""
    proj = f"+proj=utm +zone={zone} +{hemi} +ellps=WGS84 +units=m +no_defs"
    lines = gdf.loc[is_line].to_crs(proj)
    lines["geometry"] = lines.geometry.buffer(TRANSECT_BUFFER_M)
    gdf.loc[is_line, "geometry"] = lines.to_crs("EPSG:4326").geometry
    return gdf


def load_kml_plots(site_key: str) -> gpd.GeoDataFrame | None:
    """Loads KML plot polygons for a site, returns GeoDataFrame or None."""
    kml = KML_DIR / f"{site_key}.kml"
    if not kml.exists():
        return None
    try:
        gdf = gpd.read_file(kml, driver="KML").set_crs("EPSG:4326")
        gdf["geometry"] = gdf.geometry.apply(_ensure_polygon)
        gdf = _buffer_lines_to_corridors(gdf)
        gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
        gdf["plot_id"] = gdf["Name"].astype(str).str.strip()
        # Sem nenhum polígono válido (geometrias não reconhecidas) o ponto-em-polígono
        # quebraria ao calcular o centroide de uma união vazia. Devolve None para o
        # main cair no fallback por coluna em vez de travar.
        if gdf.empty:
            log.warning(f"  KML {kml.name}: 0 polígonos válidos — usando fallback")
            return None
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


# ── Local (per-site) height model with bias correction ─────────────────────
# Each site is a different region/forest type, so a curve fit on that site's
# own measured trees captures local height-diameter allometry better than
# the single pan-Amazonian Feldpausch curve — but only when there's enough
# paired data AND the DBH-height relationship in that sample actually holds.
# Below either threshold, fall back regionally. The R² gate matters because
# some sites only measured height on a narrow/biased subset of trees (e.g.
# ANA_A01: 258 measured trees all DBH>=10cm with log-log R²=0.02) — fitting
# on that subset and extrapolating to small trees would be worse than the
# regional curve, not better.
MIN_LOCAL_FIT_N = 30
MIN_LOCAL_FIT_R2 = 0.2


def _best_paired_columns(df: pd.DataFrame) -> tuple[str | None, str | None]:
    """Picks the dbh_/htot_ year-columns with the most overlapping
    (dbh>0 & htot>0) measured trees for this site."""
    dbh_cols  = [c for c in df.columns if c.startswith("dbh_")]
    htot_cols = [c for c in df.columns if c.startswith("htot_")
                 and c not in ("htot_feldpausch", "htot_estimated")]
    if not dbh_cols or not htot_cols:
        return None, None

    best_dc, best_hc, best_n = None, None, -1
    for hc in htot_cols:
        year = hc.split("_")[-1]
        dc = f"dbh_{year}" if f"dbh_{year}" in dbh_cols else dbh_cols[0]
        n = int(((pd.to_numeric(df[dc], errors="coerce") > 0) &
                 (pd.to_numeric(df[hc], errors="coerce") > 0)).sum())
        if n > best_n:
            best_dc, best_hc, best_n = dc, hc, n
    return best_dc, best_hc


def fit_local_height_model(df: pd.DataFrame) -> dict | None:
    """Fits log(Htot) ~ log(DBH) on this site's measured trees.

    Hcom (commercial height) was considered as an extra predictor, but in
    this dataset Hcom is only ever recorded for trees that also have Htot
    measured — it is never present when Htot is missing, so it cannot help
    fill the gap and was dropped. DBH is the only predictor consistently
    available on trees lacking a measured height.

    Returns None (caller falls back to regional Feldpausch) when there are
    fewer than MIN_LOCAL_FIT_N paired Htot/DBH measurements, or when the
    fitted relationship is too weak (log-log R² < MIN_LOCAL_FIT_R2).
    """
    dbh_col, htot_col = _best_paired_columns(df)
    if dbh_col is None:
        return None

    dbh  = pd.to_numeric(df[dbh_col], errors="coerce")
    htot = pd.to_numeric(df[htot_col], errors="coerce")
    mask = (dbh > 0) & (htot > 0)

    n = int(mask.sum())
    if n < MIN_LOCAL_FIT_N:
        return None

    log_dbh, log_htot = np.log(dbh[mask].to_numpy()), np.log(htot[mask].to_numpy())
    r2 = float(np.corrcoef(log_dbh, log_htot)[0, 1] ** 2)
    if r2 < MIN_LOCAL_FIT_R2:
        return None

    X = np.column_stack([np.ones(n), log_dbh])
    coef, *_ = np.linalg.lstsq(X, log_htot, rcond=None)
    resid = log_htot - X @ coef
    sigma2 = float(np.var(resid, ddof=X.shape[1])) if n > X.shape[1] else 0.0
    cf = float(np.exp(sigma2 / 2))  # Baskerville back-transform bias correction

    return {"coef": coef, "cf": cf, "dbh_col": dbh_col, "n": n, "r2": r2}


def predict_local_height(df: pd.DataFrame, model: dict) -> pd.Series:
    """Applies a fit_local_height_model() result to every row of df."""
    dbh = pd.to_numeric(df[model["dbh_col"]], errors="coerce")
    valid = dbh > 0
    log_dbh = np.log(dbh.where(valid, np.nan))

    log_h = model["coef"][0] + model["coef"][1] * log_dbh
    h = np.exp(log_h) * model["cf"]
    h[~valid] = np.nan
    return h.round(2)


def add_height_estimate_column(df: pd.DataFrame) -> pd.DataFrame:
    """Adds htot_estimated / htot_estimation_method: measured value where
    available, else a site-local Htot~DBH[+Hcom] fit, else the regional
    Feldpausch fallback (already in htot_feldpausch)."""
    htot_cols = [c for c in df.columns if c.startswith("htot_") and c != "htot_feldpausch"]
    h_meas = pd.Series(np.nan, index=df.index)
    for c in sorted(htot_cols):
        h_meas = h_meas.where(h_meas > 0, pd.to_numeric(df[c], errors="coerce"))

    model = fit_local_height_model(df)
    h_local = predict_local_height(df, model) if model is not None else \
        pd.Series(np.nan, index=df.index)

    h_regional = pd.to_numeric(df.get("htot_feldpausch", np.nan), errors="coerce")

    df["htot_estimated"] = h_meas.where(h_meas > 0, h_local.where(h_local > 0, h_regional))
    df["htot_estimation_method"] = np.where(
        h_meas > 0, "measured",
        np.where(h_local > 0, "local_fit", "feldpausch_regional"),
    )
    return df


# ── Correção do gap temporal inventário↔LiDAR via crescimento de DBH ──────────
# O inventário é medido num ano e o LiDAR voa em outro (gap mediano ~1 ano, máx 3).
# Em vez de buscar um catálogo de crescimento de ALTURA por espécie (que mal existe
# para a Amazônia e é mais ruidoso que o sinal), cresce-se o DBH até a data do voo e
# re-deriva-se a altura pela curva H-D. O incremento de DBH vem, em ordem de
# qualidade: (1) remedição da própria árvore (2 anos de DBH no site); (2) mediana
# observada do site; (3) default pooled abaixo. NÃO substitui htot_estimated — gera
# colunas NOVAS (htot_estimated_gap, dbh_lidar, dbh_incr_*) em paralelo.
DEFAULT_INCREMENT_CM_YR = 0.18   # mediana por árvore agrupando os 12 sites com remedição
MAX_INCREMENT_CM_YR     = 5.0    # clip de incrementos implausíveis (erro de medição)


def load_site_gaps() -> dict:
    """{inventory_file: (ano_lidar, gap_anos)} pelo melhor match (menor |gap|).
    Mesma regra de seleção usada em calculate_biomass."""
    if not TEMP_CSV.exists():
        return {}
    t = pd.read_csv(TEMP_CSV)
    t["abs_gap"] = t["gap_temporal_anos"].abs()
    best = (t.sort_values(["abs_gap", "ano_lidar"], ascending=[True, False])
              .groupby("nome_area_inventario", as_index=False).first())
    return {r["nome_area_inventario"]: (int(r["ano_lidar"]), float(r["gap_temporal_anos"]))
            for _, r in best.iterrows()}


def tree_dbh_increment(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Incremento anual de DBH (cm/ano) por árvore + fonte ('observed'/'site_median'/
    'default'). Negativos (erro de medição/casca) → 0; outliers → MAX_INCREMENT_CM_YR."""
    dbh_cols = sorted([c for c in df.columns if re.fullmatch(r"dbh_\d{4}", c)],
                      key=lambda c: int(c[-4:]))
    inc = pd.Series(np.nan, index=df.index)
    src = pd.Series("default", index=df.index, dtype=object)

    if len(dbh_cols) >= 2:
        y0, y1 = int(dbh_cols[0][-4:]), int(dbh_cols[-1][-4:])
        a = pd.to_numeric(df[dbh_cols[0]],  errors="coerce")
        b = pd.to_numeric(df[dbh_cols[-1]], errors="coerce")
        obs = ((b - a) / (y1 - y0)).where((a > 0) & (b > 0))
        inc = obs
        src = src.where(obs.isna(), "observed")
        site_med = obs.median()
        if pd.notna(site_med):
            fill = inc.isna()
            inc = inc.where(~fill, site_med)
            src = src.where(~fill, "site_median")

    inc = inc.where(inc.notna(), DEFAULT_INCREMENT_CM_YR)
    inc = inc.clip(lower=0.0, upper=MAX_INCREMENT_CM_YR)
    return inc, src


def add_gap_corrected_height(df: pd.DataFrame, gap: float,
                             increment: pd.Series) -> pd.DataFrame:
    """Adiciona dbh_lidar e htot_estimated_gap: DBH crescido até o ano do LiDAR e a
    altura re-derivada. Usa o gap do SITE (lidar - ano_inventário, com sinal), o mesmo
    conceito de gap do resto do pipeline. A altura é escalada por f(dbh_lidar)/f(dbh_base)
    da curva Feldpausch — exato no ramo regional, coerente com a curva no medido,
    ~decímetro no ajuste local. dbh_base = último ano de DBH (mesma base do feldpausch)."""
    # Só colunas de ano (dbh_YYYY) — evita capturar dbh_incr_cm_yr/dbh_lidar.
    dbh_cols = sorted([c for c in df.columns if re.fullmatch(r"dbh_\d{4}", c)],
                      key=lambda c: int(c[-4:]), reverse=True)
    base = dbh_cols[0] if dbh_cols else ("dbh" if "dbh" in df.columns else None)
    dbh_base = (pd.to_numeric(df[base], errors="coerce") if base is not None
                else pd.Series(np.nan, index=df.index))

    if base is None or pd.isna(gap) or gap == 0:
        # Sem gap (ou sem DBH): a estimativa corrigida coincide com a atual.
        df["dbh_lidar"] = dbh_base.round(2)
        df["htot_estimated_gap"] = pd.to_numeric(df["htot_estimated"], errors="coerce")
        return df

    # gap>0: LiDAR depois do inventário → árvore cresceu. gap<0: voo antes → menor.
    dbh_lidar = (dbh_base + increment * gap).clip(lower=1.0)
    ratio = (estimate_height_feldpausch(dbh_lidar) /
             estimate_height_feldpausch(dbh_base))
    df["dbh_lidar"] = dbh_lidar.round(2)
    df["htot_estimated_gap"] = (pd.to_numeric(df["htot_estimated"], errors="coerce")
                                * ratio).round(2)
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

    site_gaps = load_site_gaps()
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
        df = add_height_estimate_column(df)

        # Estimativa NOVA, corrigida pelo gap temporal (não substitui htot_estimated).
        lidar_year, gap = site_gaps.get(site_key, (np.nan, np.nan))
        incr, incr_src = tree_dbh_increment(df)
        df["dbh_incr_cm_yr"]  = incr.round(3)
        df["dbh_incr_source"] = incr_src
        df["gap_anos"]        = gap
        df = add_gap_corrected_height(df, gap, incr)

        out_path = OUT_DIR / f"{site_key}.csv"
        df.to_csv(out_path, index=False, encoding="utf-8")

    log.info(f"\nConcluído: {sites_done} sites, {sites_warn} warnings, {sites_err} erros")
    log.info(f"Total de árvores: {total_trees:,}")
    log.info(f"Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
