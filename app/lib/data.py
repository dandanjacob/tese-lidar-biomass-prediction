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
from plot_loading import drop_duplicate_geometries as _drop_dup_geoms


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
        g = _drop_dup_geoms(g)  # JAM_A03_2013: 16 feições = 8 parcelas duplicadas
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


# ── Qualidade geométrica das parcelas (página de outliers) ──────────────────────

def _utm_proj(lon: float, lat: float) -> str:
    """String proj4 do fuso UTM que contém (lon, lat). Mesma regra do pipeline
    (src/calculate_biomass.py) — usada para testar a posição das árvores contra o
    polígono da parcela no CRS métrico nativo do site."""
    zone = int((lon + 180) // 6) + 1
    south = "+south" if lat < 0 else ""
    return (f"+proj=utm +zone={zone} {south} +ellps=GRS80 "
            "+towgs84=0,0,0,0,0,0,0 +units=m +no_defs")


def _rect_wh(geom):
    """(largura, comprimento) em metros do retângulo de menor área que envolve o
    polígono — largura = lado menor, comprimento = lado maior. Em CRS métrico."""
    import math
    r = geom.minimum_rotated_rectangle
    if r.geom_type != "Polygon":  # degenerada → cai no bounding box
        minx, miny, maxx, maxy = geom.bounds
        return tuple(sorted([maxx - minx, maxy - miny]))
    xs, ys = r.exterior.coords.xy
    e0 = math.dist((xs[0], ys[0]), (xs[1], ys[1]))
    e1 = math.dist((xs[1], ys[1]), (xs[2], ys[2]))
    return tuple(sorted([e0, e1]))


@st.cache_data
def _trees_located_per_plot(_code_key):
    """Por (site, plot_id corrigido): nº de árvores do inventário cuja coordenada UTM
    cai DENTRO do polígono da parcela. Espacial (sjoin within) — independe de como o
    plot_id é nomeado, então funciona mesmo em sites multiparte. Sites sem coordenada
    (utm ausente) simplesmente não contribuem (contagem 0)."""
    from shapely import wkb  # noqa: F401  (garante shapely disponível)
    inv_dir = ROOT / "data/processed/04_inventory"
    feats = load_plot_features()
    counts: dict = {}
    for site, sub in feats.groupby("site"):
        inv_path = inv_dir / f"{site}.csv"
        if not inv_path.exists():
            continue
        inv = pd.read_csv(inv_path, low_memory=False)
        if not {"utm_easting", "utm_northing"}.issubset(inv.columns):
            continue
        e = pd.to_numeric(inv["utm_easting"], errors="coerce")
        n = pd.to_numeric(inv["utm_northing"], errors="coerce")
        ok = e.notna() & n.notna()
        if not ok.any():
            continue
        polys = sub.dissolve(by="plot_id").reset_index()[["plot_id", "geometry"]]
        c = polys.geometry.union_all().centroid
        utm = _utm_proj(c.x, c.y)
        polys_u = polys.to_crs(utm)
        pts = gpd.GeoDataFrame(
            geometry=gpd.points_from_xy(e[ok], n[ok]), crs=utm)
        try:
            j = gpd.sjoin(pts, polys_u, predicate="within", how="inner")
        except Exception:
            continue
        for pid, cnt in j.groupby("plot_id").size().items():
            counts[(site, pid)] = int(cnt)
    return counts


@st.cache_data
def _load_plot_quality(_code_key, _bio_mtime):
    geo = load_plot_geometries().copy()  # CRS de área-igual (métrico)
    wh = geo.geometry.apply(_rect_wh)
    geo["width_m"] = [w for w, _ in wh]
    geo["length_m"] = [h for _, h in wh]
    geo["aspect"] = geo["length_m"] / geo["width_m"].replace(0, np.nan)

    bio = load_biomass_summary()
    if not bio.empty:
        geo = geo.merge(bio[["site", "plot_id", "n_arvores"]],
                        on=["site", "plot_id"], how="left")
    else:
        geo["n_arvores"] = np.nan

    located = _trees_located_per_plot(_code_key)
    geo["n_located"] = [located.get((s, p), 0)
                        for s, p in zip(geo["site"], geo["plot_id"])]
    denom = geo["n_arvores"].where(geo["n_arvores"] > 0)
    geo["pct_pos"] = (100 * geo["n_located"] / denom).clip(upper=100)
    return geo


def load_plot_quality():
    """Geometria por parcela (área, compacidade, largura/comprimento, aspecto) + nº de
    árvores (do summary de biomassa) + % de árvores com posição confiável (caem dentro
    do polígono). Uma linha por (site, plot_id corrigido)."""
    return _load_plot_quality(
        _src_mtime(), _mtime(ROOT / "data/processed/05_biomass/summary.csv"))


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


@st.cache_data
def _usability(_code_key, _bio_mtime, _clip_mtime):
    """Categoria de aproveitamento de CADA parcela de inventário (site, plot_id):

    - "green": tem AGB calculada E nuvem recortada → entra no treino
    - "red":   cruza o LiDAR, mas sem rótulo utilizável (sem árvores separáveis
               por polígono / sem biomassa)
    - "gray":  sem sobreposição com o LiDAR

    Interseção geométrica ≠ parcela utilizável. Mesma definição usada no gráfico de
    'O que chega aos modelos' e nas cores do mapa de cobertura."""
    feats = load_plot_features()
    universe = set(zip(feats["site"].astype(str), feats["plot_id"].astype(str)))

    inter = load_intersections()
    overlap = set(zip(inter["inventory_file"].astype(str),
                      inter["plot_id"].astype(str))) & universe

    bio = load_biomass_summary()
    if not bio.empty and "agb_m1_Mg_ha" in bio.columns:
        bio = bio[bio["agb_m1_Mg_ha"].notna()]   # só rótulo válido = treinável
    agb = (set(zip(bio["site"].astype(str), bio["plot_id"].astype(str)))
           if not bio.empty else set())

    clips = load_clipped_stats()
    clipset = set(zip(clips["site"].astype(str),
                      clips["plot"].astype(str).str.replace("plot_", "", n=1)))

    green = (agb & clipset) & overlap
    return {k: ("green" if k in green else ("red" if k in overlap else "gray"))
            for k in universe}


def plot_usability():
    return _usability(
        _src_mtime(),
        _mtime(ROOT / "data/processed/05_biomass/summary.csv"),
        _mtime(ROOT / "data/processed/03_clipped_lidar/clip_summary.json"))


def training_coverage():
    """Contagens da partição verde/vermelho/cinza (deriva de plot_usability)."""
    from collections import Counter
    c = Counter(plot_usability().values())
    return {"total": sum(c.values()), "usable": c["green"],
            "unusable": c["red"], "no_lidar": c["gray"],
            "overlap": c["green"] + c["red"]}


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
                # Variante do conjunto de treino: "full" (interseções completas) ou
                # "no_outliers" (parcelas-outlier removidas). JSONs antigos não têm o
                # campo → assume "full".
                m.setdefault("variant", "no_outliers" if p.stem.endswith("_noout") else "full")
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
