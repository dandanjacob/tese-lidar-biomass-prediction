"""
Encontra, para cada parcela de inventário, os tiles de LiDAR que a cobrem.

Critério: a parcela precisa ter ≥ 99,9% da sua área dentro da cobertura CONTÍGUA de
uma única campanha LiDAR (tiles da mesma campanha, vizinhos e sem buraco entre eles,
unidos). Isso é mais permissivo (e correto) que exigir um único tile ou um `within`
estrito: uma parcela 100% coberta que apenas encosta na borda da união dos tiles
falha no `within` por causa do toque na fronteira, mas é aceita pelo critério de área.

Subcampanhas a/b do mesmo ano (ex.: JAM_A02a_2014 + JAM_A02b_2014) são tratadas como
uma única campanha — é o mesmo voo dividido em entregas, então a cobertura é contígua.

Para cada parcela qualificada, são listados todos os tiles daquela campanha que ela
toca (o recorte concatena os pontos dos vários tiles).

Saídas:
  data/processed/02_intersections/lidar_inventory_intersections.csv
  data/processed/02_intersections/intersections_temporal.csv
"""

import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from plot_loading import load_plots_dissolved

ROOT = Path(__file__).parent.parent


def _find_lidar_dir() -> Path:
    candidates = sorted((ROOT / "data/raw/lidar").glob("LiDAR_Forest_Inventory_Brazil_*"))
    if not candidates:
        raise FileNotFoundError("Diretório LiDAR não encontrado em data/raw/lidar/. Baixe os dados do ORNL DAAC.")
    return candidates[0]


LIDAR_CSV = _find_lidar_dir() / "cms_brazil_lidar_tile_inventory.csv"
KML_DIR = ROOT / "data/processed/01_kml"
OUTPUT = ROOT / "data/processed/02_intersections/lidar_inventory_intersections.csv"
TEMPORAL_OUTPUT = ROOT / "data/processed/02_intersections/intersections_temporal.csv"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def campaign_of(filename: str) -> str:
    """Campanha = nome do tile sem o sufixo do tile (_laz_N / _LAS_N / _laz_optional_N),
    com as subcampanhas a/b do mesmo ano unidas (JAM_A02a_2014 → JAM_A02_2014)."""
    name = re.sub(r"_(?:laz|LAS)_.*\.laz$", "", filename)
    return re.sub(r"(_A\d+)[a-z](_\d{4})$", r"\1\2", name)


def year_of(name: str):
    m = re.search(r"\d{4}", str(name))
    return int(m.group()) if m else None


def load_lidar_tiles() -> gpd.GeoDataFrame:
    df = pd.read_csv(LIDAR_CSV)
    geoms = [box(r.min_lon, r.min_lat, r.max_lon, r.max_lat) for r in df.itertuples()]
    g = gpd.GeoDataFrame(df[["filename"]], geometry=geoms, crs="EPSG:4326")
    g["campanha"] = g["filename"].map(campaign_of)
    return g


def main():
    print("Carregando tiles LiDAR...")
    tiles = load_lidar_tiles()
    print(f"  {len(tiles)} tiles · {tiles['campanha'].nunique()} campanhas")

    print("Carregando parcelas de inventário...")
    plots = load_plots_dissolved(KML_DIR)
    print(f"  {len(plots)} parcelas")

    # Cobertura contígua por campanha: tiles vizinhos da mesma campanha unidos.
    # Buracos (tiles faltando) viram furos no polígono → 'within' os exclui.
    camp = tiles.dissolve(by="campanha").reset_index()[["campanha", "geometry"]]

    print("Qualificando parcelas (cobertura ≥ 99,9% da área por uma campanha)...")
    # Pares candidatos (parcela × campanha que ela toca); depois mede a fração coberta.
    cand = gpd.sjoin(plots, camp, predicate="intersects", how="inner")
    camp_geom = camp.set_index("campanha")["geometry"]
    qual_keys = set()
    for r in cand.itertuples():
        cg = camp_geom[r.campanha]
        area = r.geometry.area
        if area > 0:
            ok = r.geometry.intersection(cg).area / area >= 0.999
        else:
            ok = cg.covers(r.geometry)  # parcelas-linha (sem área): cobertura topológica
        if ok:
            qual_keys.add((r.inventory_file, r.plot_id, r.campanha))

    # Tiles (por campanha) que cada parcela toca; mantém só os da campanha qualificadora.
    pt = gpd.sjoin(plots, tiles, predicate="intersects")[["inventory_file", "plot_id", "filename", "campanha"]]
    mask = [(r[0], r[1], r[3]) in qual_keys for r in pt.to_numpy()]
    pt = pt[mask]

    result = (
        pt[["inventory_file", "plot_id", "filename"]]
        .rename(columns={"filename": "laz_file"})
        .drop_duplicates()
        .sort_values(["inventory_file", "plot_id", "laz_file"])
        .reset_index(drop=True)
    )
    result.to_csv(OUTPUT, index=False)

    # CSV temporal (anos + gap) derivado dos mesmos pares.
    temp = result.rename(
        columns={"inventory_file": "nome_area_inventario", "laz_file": "nome_area_lidar"}
    ).copy()
    temp["ano_inventario"] = temp["nome_area_inventario"].map(year_of)
    temp["ano_lidar"] = temp["nome_area_lidar"].map(year_of)
    temp["gap_temporal_anos"] = temp["ano_lidar"] - temp["ano_inventario"]
    temp = temp[["nome_area_inventario", "nome_area_lidar", "plot_id",
                 "ano_inventario", "ano_lidar", "gap_temporal_anos"]]
    temp.to_csv(TEMPORAL_OUTPUT, index=False)

    print(f"\nResultado salvo em: {OUTPUT}")
    print(f"           e em:   {TEMPORAL_OUTPUT}")
    print(f"Total de pares (plot x tile): {len(result)}")
    print(f"Plots únicos com cobertura LiDAR: {result.groupby(['inventory_file', 'plot_id']).ngroups}")
    print(f"Sites de inventário cobertos: {result['inventory_file'].nunique()}")
    print(f"Tiles LiDAR utilizados: {result['laz_file'].nunique()}")


if __name__ == "__main__":
    main()
