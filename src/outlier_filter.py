"""Filtro de parcelas-outlier para o treino (variante "sem outliers").

Outlier de geometria = parcela cuja forma/área prejudica a correspondência
LiDAR×inventário no recorte. Critério (grosseiro, assumido pela tese):

    área > AREA_MAX_HA  OU  compacidade < COMP_MIN

A geometria por parcela (área-igual, compacidade = 4π·área/perímetro²) é a MESMA
de app/lib/data.py:_load_plot_geometries — dissolvida por (site, plot_id corrigido
via plot_loading.assign_plot_ids), para o treino nunca divergir do que o app mostra.

Acionado por variável de ambiente, para não tocar na lógica dos scripts de treino:

    EXCLUDE_OUTLIERS=1   → ativa o filtro e usa o sufixo "_noout" nas saídas

Uso nos train_*.py:
    from outlier_filter import filter_summary, SUFFIX, VARIANT
    df = filter_summary(pd.read_csv(SUMMARY))      # no-op se a flag estiver off
    ...salvar em  f"cv_results_{key}{SUFFIX}.csv", etc.
"""

import os
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
KML_DIR = ROOT / "data/processed/01_kml"
EQUAL_AREA = ("+proj=aea +lat_1=-5 +lat_2=-42 +lat_0=-32 +lon_0=-60 "
              "+datum=WGS84 +units=m +no_defs")

# Critério de outlier (fonte única; espelhado no texto da página do app).
AREA_MAX_HA = 0.5
COMP_MIN = 0.6

# Estado da variante, lido do ambiente (uma vez por processo).
EXCLUDE = os.environ.get("EXCLUDE_OUTLIERS") == "1"
SUFFIX = "_noout" if EXCLUDE else ""
VARIANT = "no_outliers" if EXCLUDE else "full"


@lru_cache(maxsize=1)
def plot_geometry() -> "gpd.GeoDataFrame":
    """Uma linha por (site, plot_id corrigido): area_ha, compacidade. Igual ao app."""
    import sys
    src = str(ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from plot_loading import assign_plot_ids, drop_duplicate_geometries

    frames = []
    for kml in KML_DIR.glob("*.kml"):
        if "lidar" in kml.name:
            continue
        try:
            g = gpd.read_file(kml, driver="KML").set_crs("EPSG:4326")
        except Exception:
            continue
        g = g[g.geometry.notna() & ~g.geometry.is_empty].reset_index(drop=True)
        if g.empty:
            continue
        g = drop_duplicate_geometries(g)  # JAM_A03_2013: feições duplicadas
        g["site"] = kml.stem
        g["plot_id"] = assign_plot_ids(g["Name"])
        frames.append(g[["site", "plot_id", "geometry"]])

    import pandas as pd
    gdf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
    gdf = gdf.to_crs(EQUAL_AREA).dissolve(by=["site", "plot_id"]).reset_index()
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    gdf["area_ha"] = gdf.geometry.area / 10_000
    gdf["compacidade"] = (4 * np.pi * gdf.geometry.area) / (gdf.geometry.length ** 2)
    return gdf


@lru_cache(maxsize=1)
def excluded_keys(area_max_ha: float = AREA_MAX_HA,
                  comp_min: float = COMP_MIN) -> frozenset:
    """Conjunto de (site, str(plot_id)) que são outliers pelo critério."""
    g = plot_geometry()
    out = g[(g["area_ha"] > area_max_ha) | (g["compacidade"] < comp_min)]
    return frozenset((s, str(p)) for s, p in zip(out["site"], out["plot_id"]))


def filter_summary(df):
    """Remove as linhas-outlier do summary. No-op quando EXCLUDE_OUTLIERS != 1."""
    if not EXCLUDE:
        return df
    drop = excluded_keys()
    keep = [(s, str(p)) not in drop for s, p in zip(df["site"], df["plot_id"])]
    return df[keep].copy()


if __name__ == "__main__":
    import pandas as pd
    g = plot_geometry()
    summ = pd.read_csv(ROOT / "data/processed/05_biomass/summary.csv")
    summ = summ[summ["agb_m1_Mg_ha"].notna()]
    # só as parcelas treináveis (têm .laz recortado)
    laz = ROOT / "data/processed/03_clipped_lidar"
    trainable = [(r.site, str(r.plot_id)) for r in summ.itertuples()
                 if (laz / r.site / f"plot_{r.plot_id}.laz").exists()]
    tset = set(trainable)
    gg = g[[(s, str(p)) in tset for s, p in zip(g["site"], g["plot_id"])]]
    OR = gg[(gg.area_ha > AREA_MAX_HA) | (gg.compacidade < COMP_MIN)]
    AND = gg[(gg.area_ha > AREA_MAX_HA) & (gg.compacidade < COMP_MIN)]
    print(f"parcelas treináveis: {len(tset)}")
    print(f"  OR  (área>{AREA_MAX_HA} OU comp<{COMP_MIN}):  remove {len(OR)}  -> sobra {len(tset)-len(OR)}")
    print(f"  AND (área>{AREA_MAX_HA} E  comp<{COMP_MIN}):  remove {len(AND)}  -> sobra {len(tset)-len(AND)}")
    print("  sites afetados (OR):", sorted(OR.site.str.replace(r'_inventory.*','',regex=True).unique()))
