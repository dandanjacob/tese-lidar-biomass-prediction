"""Carregadores de dados (cacheados). Sem texto de interface — só dados."""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]

# Regra de plot_id vem do pipeline (fonte única) — assim o app nunca diverge dos CSVs.
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
from plot_loading import assign_plot_ids as _assign_plot_ids


def _mtime(path: Path) -> float:
    """mtime do arquivo (0 se ausente). Usado como chave de cache: quando o CSV é
    regerado no disco, o mtime muda e o @st.cache_data relê automaticamente."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _src_mtime() -> float:
    """Chave de cache do CÓDIGO: maior mtime entre este arquivo e src/plot_loading.py.
    As caches derivadas de KML (plot_id, cobertura) leem KMLs estáticos, então o que muda
    o resultado é a LÓGICA. O @st.cache_data não hasheia funções auxiliares/importadas;
    sem esta chave, uma mudança em assign_plot_ids/cobertura deixaria a cache defasada
    (era o bug do mapa todo cinza após o reprocessamento)."""
    return max(_mtime(Path(__file__)), _mtime(_SRC / "plot_loading.py"))


@st.cache_data
def _read_intersections(_mtime_key):
    return pd.read_csv(ROOT / "data/processed/02_intersections/lidar_inventory_intersections.csv")


def load_intersections():
    return _read_intersections(_mtime(ROOT / "data/processed/02_intersections/lidar_inventory_intersections.csv"))


@st.cache_data
def _read_temporal(_mtime_key):
    df = pd.read_csv(ROOT / "data/processed/02_intersections/intersections_temporal.csv")
    df["campanha_lidar"] = df["nome_area_lidar"].str.extract(r"^(.+)_\d+\.laz$")[0]
    df["abs_gap"] = df["gap_temporal_anos"].abs()
    return df


def load_temporal():
    return _read_temporal(_mtime(ROOT / "data/processed/02_intersections/intersections_temporal.csv"))


def _ensure_polygon(geom):
    """(Multi)LineString de anel fechado (ex.: FNA) → polígono, para a parcela ter
    área (quadrado no mapa, geometria válida). Linhas abertas ficam como estão."""
    from shapely.ops import polygonize, unary_union
    if geom is None or geom.is_empty:
        return geom
    if geom.geom_type in ("LineString", "MultiLineString"):
        polys = list(polygonize(geom))
        if polys:
            return unary_union(polys)
    return geom


def _corrected_plot_id(gdf):
    """plot_id único por feature — usa a regra canônica do pipeline
    (src/plot_loading.py:assign_plot_ids) para o app nunca divergir dos CSVs."""
    return _assign_plot_ids(gdf["Name"])


@st.cache_data
def _load_plot_features(_code_key):
    """Uma linha por polígono: site, plot_id (corrigido), geometry (EPSG:4326)."""
    frames = []
    for kml in (ROOT / "data/processed/01_kml").glob("*.kml"):
        if "lidar" in kml.name:
            continue
        try:
            g = gpd.read_file(kml, driver="KML").set_crs("EPSG:4326")
        except Exception:
            continue
        g = g[g.geometry.notna() & ~g.geometry.is_empty].reset_index(drop=True)
        if g.empty:
            continue
        g["geometry"] = g.geometry.apply(_ensure_polygon)
        g["site"] = kml.stem
        g["plot_id"] = _corrected_plot_id(g)
        frames.append(g[["site", "plot_id", "geometry"]])
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")


def load_plot_features():
    return _load_plot_features(_src_mtime())


@st.cache_data
def _load_plot_geometries(_code_key):
    EQUAL_AREA = "+proj=aea +lat_1=-5 +lat_2=-42 +lat_0=-32 +lon_0=-60 +datum=WGS84 +units=m +no_defs"
    gdf_ea = load_plot_features().to_crs(EQUAL_AREA).dissolve(by=["site", "plot_id"]).reset_index()
    # filtra geometrias degeneradas (LineString, GeometryCollection) que não têm área
    gdf_ea = gdf_ea[gdf_ea.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    gdf_ea["area_ha"] = gdf_ea.geometry.area / 10_000
    gdf_ea["perimeter_m"] = gdf_ea.geometry.length
    gdf_ea["compacidade"] = (4 * np.pi * gdf_ea.geometry.area) / (gdf_ea["perimeter_m"] ** 2)
    return gdf_ea


def load_plot_geometries():
    return _load_plot_geometries(_src_mtime())


@st.cache_data
def _inventory_plot_counts(_code_key):
    """Nº de parcelas distintas por site, com plot_id corrigido (ver _corrected_plot_id).
    Consistente com as interseções (sempre inventário ≥ interseção)."""
    return load_plot_features().groupby("site")["plot_id"].nunique().rename("n_plots")


def inventory_plot_counts():
    return _inventory_plot_counts(_src_mtime())


@st.cache_data
def _coverage_geom(_code_key):
    """Cobertura do inventário pelo LiDAR (nível parcela, plot_id corrigido).

    Espelha o critério do pipeline (find_intersections): a parcela precisa ter ≥ 99,9%
    da sua área dentro da cobertura CONTÍGUA de uma campanha (tiles vizinhos da mesma
    campanha unidos, com subcampanhas a/b do mesmo ano juntas), não de um tile isolado.

    - total / kept (cobertura ≥ 99,9%) / discarded (sobrepõe, mas < 99,9%) / no_overlap
    - corrupt_inventory: KMLs que falharam na leitura
    - corrupt_pointclouds / plots_no_points: de clip_summary.json, quando disponível.
    """
    import re

    from shapely.geometry import box

    lidar_dir = sorted((ROOT / "data/raw/lidar").glob("LiDAR_Forest_Inventory_Brazil_*"))[0]
    md = pd.read_csv(lidar_dir / "cms_brazil_lidar_tile_inventory.csv")
    md["campanha"] = (
        md["filename"]
        .str.replace(r"_(?:laz|LAS)_.*\.laz$", "", regex=True)
        .str.replace(r"(_A\d+)[a-z](_\d{4})$", r"\1\2", regex=True)  # une subcampanhas a/b
    )
    tiles = gpd.GeoDataFrame(
        md[["filename", "campanha"]],
        geometry=[box(r.min_lon, r.min_lat, r.max_lon, r.max_lat) for r in md.itertuples()],
        crs="EPSG:4326",
    )
    camp = tiles.dissolve(by="campanha").reset_index()[["campanha", "geometry"]]

    plots = load_plot_features().dissolve(by=["site", "plot_id"]).reset_index()
    plots["pid"] = range(len(plots))
    # kept = ≥ 99,9% da área da parcela dentro da cobertura de uma campanha (espelha o pipeline)
    camp_geom = camp.set_index("campanha")["geometry"]
    cand = gpd.sjoin(plots, camp, predicate="intersects")
    covered = set()
    for r in cand.itertuples():
        cg = camp_geom[r.campanha]
        area = r.geometry.area
        ok = (r.geometry.intersection(cg).area / area >= 0.999) if area > 0 else cg.covers(r.geometry)
        if ok:
            covered.add(r.pid)
    i = set(gpd.sjoin(plots, tiles, predicate="intersects")["pid"])
    plots["w"] = plots["pid"].isin(covered)
    plots["i"] = plots["pid"].isin(i)

    corrupt_inv = 0
    for kml in (ROOT / "data/processed/01_kml").glob("*.kml"):
        if "lidar" in kml.name:
            continue
        try:
            gpd.read_file(kml, driver="KML")
        except Exception:
            corrupt_inv += 1

    return {
        "total": int(len(plots)),
        "kept": int(plots["w"].sum()),
        "discarded": int((~plots["w"] & plots["i"]).sum()),
        "no_overlap": int((~plots["w"] & ~plots["i"]).sum()),
        "corrupt_inventory": int(corrupt_inv),
        "corrupt_pointclouds": None,
        "plots_no_points": None,
    }


def coverage_stats():
    """Parte geométrica (cacheada) + leitura fresca do clip_summary.json (muda após o
    re-clip), para os corrompidos/vazias refletirem sempre o último recorte."""
    stats = dict(_coverage_geom(_src_mtime()))
    summary = ROOT / "data/processed/03_clipped_lidar/clip_summary.json"
    if summary.exists():
        try:
            import json
            s = json.loads(summary.read_text())
            stats["corrupt_pointclouds"] = s.get("corrupt_tiles")
            stats["plots_no_points"] = s.get("plots_no_points")
        except Exception:
            pass
    return stats


# Sem cache: o conjunto de clips muda no disco (re-clip) e o scan é barato — assim a
# lista nunca fica defasada (evita oferecer no app um .laz que já foi removido).
def load_clipped_stats():
    clipped_dir = ROOT / "data/processed/03_clipped_lidar"
    files = list(clipped_dir.rglob("*.laz"))
    rows = [{"site": f.parent.name, "plot": f.stem, "path": str(f),
             "size_mb": f.stat().st_size / 1e6} for f in files]
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["site", "plot", "path", "size_mb"])


@st.cache_data
def _load_biomass_summary(_mtime_key):
    path = ROOT / "data/processed/05_biomass/summary.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["plot_id"] = df["plot_id"].astype(str)
    df["site_short"] = df["site"].str.replace(r"_inventory_plots|_inventory", "", regex=True)
    return df


def load_biomass_summary():
    # mtime do CSV como chave: regerar o summary.csv (re-run da biomassa) invalida o cache.
    return _load_biomass_summary(_mtime(ROOT / "data/processed/05_biomass/summary.csv"))


_MODEL_DIR = ROOT / "data/processed/06_model"


def load_models() -> list:
    """Todos os modelos treinados (model_metrics*.json em 06_model/), ordenados.
    Cada um traz hiperparâmetros, métricas globais LOSO e o nome do seu cv_results."""
    out = []
    if _MODEL_DIR.exists():
        import json
        for p in sorted(_MODEL_DIR.glob("model_metrics*.json")):
            try:
                m = json.loads(p.read_text())
                m.setdefault("key", p.stem.replace("model_metrics", "").strip("_") or "gbr")
                m.setdefault("cv_file", "cv_results.csv")
                out.append(m)
            except Exception:
                pass
    return out


@st.cache_data
def _load_cv(_mtime_key, fname):
    path = _MODEL_DIR / fname
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def load_cv_results(fname="cv_results.csv"):
    return _load_cv(_mtime(_MODEL_DIR / fname), fname)


@st.cache_data
def best_match(temporal_df):
    return (
        temporal_df.sort_values(["abs_gap", "ano_lidar"], ascending=[True, False])
        .groupby(["nome_area_inventario", "plot_id"], as_index=False)
        .first()
    )


def merged_geo(temporal_df, plots_geo):
    bst = best_match(temporal_df)
    return (
        bst.merge(plots_geo.rename(columns={"site": "nome_area_inventario"}),
                  on=["nome_area_inventario", "plot_id"], how="inner")
    )
