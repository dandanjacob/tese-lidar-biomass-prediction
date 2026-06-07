"""
Calculates individual aboveground carbon (IAGC, kg C) for each tree in the
processed inventory files, and produces a per-plot summary table.

Three models (Longo et al. 2016):
  M1 — simplest : all trees, mean wood density, single Chave 2014 equation
  M2 — medium   : live trees / dead trees / palms with separate equations;
                   mean wood density (no species distinction)
  M3 — full     : same as M2 but species-specific wood density
                   (Zanne/Chave GWDD; fallback genus → site mean → 0.6)

Equations (f_C = 0.5):
  Live trees  : IAGC = 0.0673 * f_C * (rho_w * DBH² * H_t)^0.976   [Chave 2014]
  Dead trees  : IAGC = 0.1007 * f_C * rho_s * DBH² * H_t^0.818     [Chambers 2000]
  Live palms  : IAGC = 0.03781 * f_C * DBH^2.7483                   [Goodman 2013]

Height (H_t): measured htot_{year} when available, else htot_feldpausch.
Wood density: Zanne/Chave GWDD lookup (species → genus → site mean → 0.6 g/cm³).
Snag density: 0.40 g/cm³ (Palace et al. 2007, mean for Amazon snags).

Outputs:
  data/processed/05_biomass/{site}.csv   — per-tree with new IAGC columns
  data/processed/05_biomass/summary.csv  — per-plot summary table
"""

import logging
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

from plot_loading import assign_plot_ids, drop_duplicate_geometries

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

ROOT       = Path(__file__).parent.parent
INV_DIR    = ROOT / "data/processed/04_inventory"
TEMP_CSV   = ROOT / "data/processed/02_intersections/intersections_temporal.csv"
KML_DIR    = ROOT / "data/processed/01_kml"
WD_SPECIES = ROOT / "data/raw/wood_density_species.csv"
WD_GENUS   = ROOT / "data/raw/wood_density_genus.csv"
OUT_DIR    = ROOT / "data/processed/05_biomass"

# Constants
F_C        = 0.5    # carbon fraction of dry biomass (Baccini et al. 2012)
RHO_W_MEAN = 0.6   # mean tropical wood density g/cm³ (fallback)
RHO_S      = 0.40  # snag density g/cm³ (Palace et al. 2007)
EQUAL_AREA = "+proj=aea +lat_1=-5 +lat_2=-42 +lat_0=-32 +lon_0=-60 +datum=WGS84 +units=m +no_defs"


# ── Wood density lookup ────────────────────────────────────────────────────────

def build_wd_lookup() -> tuple[dict, dict]:
    sp = pd.read_csv(WD_SPECIES)
    gn = pd.read_csv(WD_GENUS)
    sp_dict = dict(zip(sp["species"].str.lower().str.strip(), sp["wood_density"]))
    gn_dict = dict(zip(gn["genus"].str.lower().str.strip(),   gn["wood_density"]))
    return sp_dict, gn_dict


def lookup_wood_density(sci_name: str, sp_dict: dict, gn_dict: dict,
                        fallback: float = RHO_W_MEAN) -> float:
    if not isinstance(sci_name, str) or sci_name.strip() == "":
        return fallback
    name = sci_name.lower().strip()
    if name in sp_dict:
        return sp_dict[name]
    genus = name.split()[0]
    if genus in gn_dict:
        return gn_dict[genus]
    return fallback


# ── Biomass equations ──────────────────────────────────────────────────────────

def iagc_chave2014(dbh, htot, rho_w):
    """Live tree — Chave et al. 2014 Eq. 7 (kg C)."""
    return 0.0673 * F_C * (rho_w * dbh**2 * htot)**0.976


def iagc_chambers2000(dbh, htot, rho_s=RHO_S):
    """Dead tree (snag) — Chambers et al. 2000 (kg C)."""
    return 0.1007 * F_C * rho_s * dbh**2 * htot**0.818


def iagc_goodman2013(dbh):
    """Live palm — Goodman et al. 2013 (kg C)."""
    return 0.03781 * F_C * dbh**2.7483


# ── Per-tree biomass calculation ───────────────────────────────────────────────

def pick_best_year_col(cols, prefix, lidar_year):
    suffixed = [c for c in cols if re.match(rf"^{prefix}_\d{{4}}$", c)]
    if not suffixed:
        return prefix if prefix in cols else None
    return min(suffixed, key=lambda c: abs(int(c.split("_")[-1]) - lidar_year))


def prepare_tree_data(df: pd.DataFrame, lidar_year: int) -> pd.DataFrame:
    """Selects best-year DBH / htot and resolves dead / type columns."""
    cols = df.columns.tolist()

    dbh_col  = pick_best_year_col(cols, "dbh",  lidar_year)
    htot_col = pick_best_year_col(cols, "htot", lidar_year)
    dead_col = pick_best_year_col(cols, "dead", lidar_year)
    type_col = pick_best_year_col(cols, "type", lidar_year)

    out = df.copy()
    out["dbh_used"]  = pd.to_numeric(df[dbh_col],  errors="coerce") if dbh_col  else np.nan
    out["dead_used"] = df[dead_col].map(lambda v: str(v).strip().lower() in
                       ("true","1","yes","a","dead","mort")) if dead_col else False
    out["type_used"] = df[type_col].astype(str).str.strip().str.upper() if type_col else "O"

    # Height: prefer measured, fallback to Feldpausch estimate
    h_meas = pd.to_numeric(df[htot_col], errors="coerce") if htot_col else pd.Series(np.nan, index=df.index)
    h_feld = pd.to_numeric(df.get("htot_feldpausch", pd.Series(np.nan, index=df.index)), errors="coerce")
    out["htot_used"]   = h_meas.where(h_meas > 0, h_feld)
    out["htot_source"] = np.where(h_meas > 0, "measured", "feldpausch")

    return out


def calc_biomass(df: pd.DataFrame, sp_dict: dict, gn_dict: dict,
                 site_mean_wd: float) -> pd.DataFrame:
    """Adds iagc_m1_kgC, iagc_m2_kgC, iagc_m3_kgC columns."""

    dbh  = df["dbh_used"]
    htot = df["htot_used"]
    dead = df["dead_used"]
    typ  = df["type_used"]

    valid_dh  = dbh.notna() & (dbh > 0) & htot.notna() & (htot > 0)
    valid_d   = dbh.notna() & (dbh > 0)
    is_palm   = typ == "P"
    is_dead   = dead == True
    is_alive  = ~is_dead

    # ── Model 1: all trees, Chave 2014, mean rho_w ──────────────────────────
    m1 = pd.Series(np.nan, index=df.index)
    mask = valid_dh
    m1[mask] = iagc_chave2014(dbh[mask], htot[mask], RHO_W_MEAN)
    df["iagc_m1_kgC"] = m1.round(4)

    # ── Model 2: live trees / dead trees / palms, mean rho_w ─────────────────
    m2 = pd.Series(np.nan, index=df.index)
    # live trees
    lv = valid_dh & ~is_palm & is_alive
    m2[lv] = iagc_chave2014(dbh[lv], htot[lv], RHO_W_MEAN)
    # dead trees
    dt = valid_dh & ~is_palm & is_dead
    m2[dt] = iagc_chambers2000(dbh[dt], htot[dt])
    # live palms (no height needed)
    lp = valid_d & is_palm & is_alive
    m2[lp] = iagc_goodman2013(dbh[lp])
    df["iagc_m2_kgC"] = m2.round(4)

    # ── Model 3: same as M2 but species-specific rho_w ───────────────────────
    sci = df.get("scientific_name", pd.Series("", index=df.index)).fillna("")
    rho = sci.apply(lambda s: lookup_wood_density(s, sp_dict, gn_dict, site_mean_wd))
    df["rho_w_m3"] = rho.round(4)

    m3 = pd.Series(np.nan, index=df.index)
    m3[lv] = iagc_chave2014(dbh[lv], htot[lv], rho[lv])
    m3[dt] = iagc_chambers2000(dbh[dt], htot[dt])
    m3[lp] = iagc_goodman2013(dbh[lp])
    df["iagc_m3_kgC"] = m3.round(4)

    return df


# ── Plot area from KML ─────────────────────────────────────────────────────────

def _ensure_polygon(geom):
    """(Multi)LineString de anel fechado → polígono. KMLs como FNA/TAP trazem parcelas
    como LINHAS: sem isto a área dá 0 (linha não tem área) → AGB = soma/0 = NaN."""
    from shapely.ops import polygonize, unary_union
    if geom is None or geom.is_empty:
        return geom
    if geom.geom_type in ("LineString", "MultiLineString"):
        polys = list(polygonize(geom))
        if polys:
            return unary_union(polys)
    return geom


def plot_areas(site_key: str) -> dict:
    """Returns {plot_id: area_ha} from KML geometry."""
    kml = KML_DIR / f"{site_key}.kml"
    if not kml.exists():
        return {}
    try:
        gdf = gpd.read_file(kml, driver="KML").set_crs("EPSG:4326")
        gdf["geometry"] = gdf.geometry.apply(_ensure_polygon)
        gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(EQUAL_AREA)
        gdf["plot_id"] = gdf["Name"].astype(str).str.strip()
        gdf = gdf.dissolve(by="plot_id").reset_index()
        return dict(zip(gdf["plot_id"], (gdf.geometry.area / 10_000).round(4)))
    except Exception:
        return {}


# ── Atribuição de árvores às quadras (split espacial) ───────────────────────────

def _utm_proj(lon: float, lat: float) -> str:
    zone = int((lon + 180) // 6) + 1
    south = "+south" if lat < 0 else ""
    return (f"+proj=utm +zone={zone} {south} +ellps=GRS80 "
            "+towgs84=0,0,0,0,0,0,0 +units=m +no_defs")


def quadra_geoms(site_key: str):
    """GeoDataFrame das quadras do site em UTM: colunas name (Name), quadra (plot_id),
    geometry. Usa a mesma regra de plot_id do pipeline (assign_plot_ids). Retorna None
    se não houver KML/geometria."""
    kml = KML_DIR / f"{site_key}.kml"
    if not kml.exists():
        return None
    try:
        g = gpd.read_file(kml, driver="KML").set_crs("EPSG:4326")
    except Exception:
        return None
    g["geometry"] = g.geometry.apply(_ensure_polygon)
    g = g[g.geometry.notna() & ~g.geometry.is_empty
          & g.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].reset_index(drop=True)
    if g.empty:
        return None
    g = drop_duplicate_geometries(g)  # JAM_A03_2013: feições duplicadas → 1 só por quadra
    g["name"] = g["Name"].astype(str).str.strip()
    g["quadra"] = assign_plot_ids(g["Name"])
    c = g.geometry.union_all().centroid
    return g.to_crs(_utm_proj(c.x, c.y))[["name", "quadra", "geometry"]]


def assign_quadras(df: pd.DataFrame, quadras: gpd.GeoDataFrame) -> pd.Series:
    """Para cada árvore, o id da quadra em que cai, RESTRITO às quadras do seu próprio
    `Name` de campo (plot_id) — assim o split nunca cruza parcelas-de-campo distintas.
    Dentro das candidatas: contém → se várias (quadras sobrepostas), centroide mais
    próximo; se nenhuma, polígono mais próximo. NaN se sem coordenada ou Name sem quadra."""
    east = pd.to_numeric(df["utm_easting"], errors="coerce")
    north = pd.to_numeric(df["utm_northing"], errors="coerce")
    field = df["plot_id"].astype(str).str.strip()
    by_name = {nm: sub for nm, sub in quadras.groupby("name")}
    out = pd.Series(index=df.index, dtype=object)
    for idx in df.index:
        x, y = east[idx], north[idx]
        cand = by_name.get(field[idx])
        if pd.isna(x) or pd.isna(y) or cand is None or len(cand) == 0:
            continue
        pt = Point(x, y)
        inside = cand[cand.geometry.contains(pt)]
        if len(inside) == 1:
            out[idx] = inside.iloc[0]["quadra"]
        elif len(inside) > 1:
            out[idx] = inside.loc[inside.geometry.centroid.distance(pt).idxmin(), "quadra"]
        else:
            out[idx] = cand.loc[cand.geometry.distance(pt).idxmin(), "quadra"]
    return out


# ── Summary table ──────────────────────────────────────────────────────────────

def build_summary(df: pd.DataFrame, site_key: str, areas: dict,
                  lidar_year: int, gap: float) -> pd.DataFrame:
    rows = []
    for pid, grp in df.groupby("plot_id"):
        area = areas.get(str(pid), np.nan)
        n    = len(grp)
        n_live_trees = int(((grp["type_used"] == "O") & (~grp["dead_used"])).sum())
        n_dead       = int(((grp["type_used"] == "O") &  (grp["dead_used"])).sum())
        n_palms      = int((grp["type_used"] == "P").sum())

        def agc_ha(col):
            s = grp[col].sum()
            return round(s / 1000 / area, 4) if area and area > 0 else np.nan

        def agb_ha(col):
            v = agc_ha(col)
            return round(v / F_C, 4) if not np.isnan(v) else np.nan

        rows.append({
            "site":           site_key,
            "plot_id":        pid,
            "area_ha":        area,
            "n_arvores":      n,
            "n_arvores_vivas":n_live_trees,
            "n_mortas":       n_dead,
            "n_palmeiras":    n_palms,
            "ano_lidar":      lidar_year,
            "gap_anos":       gap,
            # Model 1
            "n_m1":           int(grp["iagc_m1_kgC"].notna().sum()),
            "agc_m1_MgC_ha":  agc_ha("iagc_m1_kgC"),
            "agb_m1_Mg_ha":   agb_ha("iagc_m1_kgC"),
            # Model 2
            "n_m2":           int(grp["iagc_m2_kgC"].notna().sum()),
            "agc_m2_MgC_ha":  agc_ha("iagc_m2_kgC"),
            "agb_m2_Mg_ha":   agb_ha("iagc_m2_kgC"),
            # Model 3
            "n_m3":           int(grp["iagc_m3_kgC"].notna().sum()),
            "agc_m3_MgC_ha":  agc_ha("iagc_m3_kgC"),
            "agb_m3_Mg_ha":   agb_ha("iagc_m3_kgC"),
            "rho_w_m3_mean":  round(grp["rho_w_m3"].mean(), 4),
        })
    return pd.DataFrame(rows)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Carregando banco de densidade da madeira (GWDD)...")
    sp_dict, gn_dict = build_wd_lookup()
    log.info(f"  {len(sp_dict):,} espécies · {len(gn_dict):,} gêneros")

    temp = pd.read_csv(TEMP_CSV)
    temp["abs_gap"] = temp["gap_temporal_anos"].abs()
    best = (temp.sort_values(["abs_gap", "ano_lidar"], ascending=[True, False])
            .groupby("nome_area_inventario", as_index=False).first())
    lidar_yr_map = dict(zip(best["nome_area_inventario"], best["ano_lidar"].astype(int)))
    gap_map      = dict(zip(best["nome_area_inventario"], best["gap_temporal_anos"]))

    all_summaries = []

    for csv in sorted(INV_DIR.glob("*.csv")):
        if csv.name == "README.md":
            continue
        site_key  = csv.stem
        lidar_yr  = lidar_yr_map.get(site_key, 2015)
        gap       = gap_map.get(site_key, np.nan)

        df = pd.read_csv(csv, low_memory=False)
        if df.empty:
            continue

        df = prepare_tree_data(df, lidar_yr)

        # Site mean wood density (fallback for M3 when species/genus not in GWDD)
        sci = df.get("scientific_name", pd.Series("", index=df.index)).fillna("")
        known = sci.apply(lambda s: lookup_wood_density(s, sp_dict, gn_dict, np.nan))
        site_mean_wd = known.dropna().mean() if known.notna().any() else RHO_W_MEAN
        if np.isnan(site_mean_wd):
            site_mean_wd = RHO_W_MEAN

        df = calc_biomass(df, sp_dict, gn_dict, site_mean_wd)

        if "plot_id" not in df.columns:
            df["plot_id"] = "unknown"

        # Split por QUADRA: atribui cada árvore à quadra pela posição (utm_easting/northing),
        # refinando a parcela-de-campo (Name) nas quadras que a compõem. Só para sites
        # multipartes (Name repetido); nos demais a quadra já é o próprio Name.
        quadras = quadra_geoms(site_key)
        df["quadra_id"] = np.nan
        multipart = (quadras is not None and quadras["name"].nunique() < len(quadras)
                     and {"utm_easting", "utm_northing"}.issubset(df.columns))
        if multipart:
            qid = assign_quadras(df, quadras)
            df["quadra_id"] = qid
            frac = float(qid.notna().mean())
            if frac >= 0.5:
                areas = dict(zip(quadras["quadra"], (quadras.geometry.area / 10_000).round(4)))
                df_sum = df[qid.notna()].copy()
                df_sum["plot_id"] = qid[qid.notna()].astype(str)
                n_drop = len(df) - len(df_sum)
                log.info(f"      quadras: {df_sum['plot_id'].nunique()} parcelas · "
                         f"{frac:.0%} árvores localizadas"
                         + (f" · {n_drop} sem coordenada descartadas" if n_drop else ""))
            else:  # zona UTM provavelmente errada → não arrisca o split
                log.warning(f"      {site_key}: só {frac:.0%} localizadas — mantendo nível de parcela")
                areas, df_sum = plot_areas(site_key), df
        else:
            areas, df_sum = plot_areas(site_key), df

        # Save per-tree file (inclui quadra_id quando houve split)
        df.to_csv(OUT_DIR / f"{site_key}.csv", index=False, encoding="utf-8")

        summary = build_summary(df_sum, site_key, areas, lidar_yr, gap)
        all_summaries.append(summary)

        n_m1 = df["iagc_m1_kgC"].notna().sum()
        n_m2 = df["iagc_m2_kgC"].notna().sum()
        n_m3 = df["iagc_m3_kgC"].notna().sum()
        log.info(f"  [OK] {site_key:<50} M1={n_m1} M2={n_m2} M3={n_m3} árvores")

    summary_df = pd.concat(all_summaries, ignore_index=True)
    summary_df.to_csv(OUT_DIR / "summary.csv", index=False, encoding="utf-8")

    log.info(f"\nSummary: {len(summary_df)} plots · {OUT_DIR / 'summary.csv'}")
    log.info(f"\n{'Campo':<20} {'M1':>10} {'M2':>10} {'M3':>10}")
    log.info(f"{'Plots com área':<20} {summary_df.agc_m1_MgC_ha.notna().sum():>10} "
             f"{summary_df.agc_m2_MgC_ha.notna().sum():>10} "
             f"{summary_df.agc_m3_MgC_ha.notna().sum():>10}")
    log.info(f"{'AGC médio MgC/ha':<20} {summary_df.agc_m1_MgC_ha.mean():>10.2f} "
             f"{summary_df.agc_m2_MgC_ha.mean():>10.2f} "
             f"{summary_df.agc_m3_MgC_ha.mean():>10.2f}")


if __name__ == "__main__":
    main()
