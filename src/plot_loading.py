"""Carregamento das parcelas de inventário com plot_id corrigido.

Regra do plot_id — CADA FEATURE (quadra) É UMA PARCELA:
- Cada polígono do KML vira uma parcela distinta com plot_id único. Sites como CAU
  (176 quadras sob 22 nomes) ou FST (40 quadras sob 5 nomes) têm várias quadras
  compartilhando o mesmo `Name`; cada uma é uma parcela independente — não são partes
  de uma só parcela.
- Construção do plot_id:
  - `Name` único no site → usa o próprio `Name`.
  - `Name` repetido (várias quadras com o mesmo nome) → `Name_k` (k de 1..n).
  - `Name` totalmente não informativo (um único valor para todas as features, ex.:
    JAM_A02_2013 com 48 polígonos "0") → índice sequencial '0'..'n-1'.

Usado por src/find_intersections.py e src/clip_lidar_to_plots.py para manter a mesma
definição de parcela em todo o pipeline. O app (app/lib/data.py) espelha esta regra.
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.ops import polygonize, unary_union


def _ensure_polygon(geom):
    """Alguns KMLs trazem a parcela como (Multi)LineString. Se as linhas forem anéis
    fechados (ex.: FNA_A01_2013), converte para polígono — assim a parcela tem área
    (vira quadrado no mapa e recorta pontos). Linhas abertas ficam como estão."""
    if geom is None or geom.is_empty:
        return geom
    if geom.geom_type in ("LineString", "MultiLineString"):
        polys = list(polygonize(geom))
        if polys:
            return unary_union(polys)
    return geom


def assign_plot_ids(names) -> list[str]:
    """plot_id único por feature (ver regra no topo do módulo).

    Espelhado em app/lib/data.py — manter as duas implementações idênticas.
    """
    names = [str(n).strip() for n in names]  # ' 1' e '1' são a mesma quadra
    if len(set(names)) == 1 and len(names) > 1:
        return [str(i) for i in range(len(names))]  # Name não informativo
    counts: dict[str, int] = {}
    for n in names:
        counts[n] = counts.get(n, 0) + 1
    seen: dict[str, int] = {}
    out = []
    for n in names:
        if counts[n] == 1:
            out.append(n)
        else:
            seen[n] = seen.get(n, 0) + 1
            out.append(f"{n}_{seen[n]}")  # quadras sob o mesmo Name
    return out


def load_plots(kml_dir) -> gpd.GeoDataFrame:
    """Uma linha por polígono/parcela. Colunas: inventory_file, plot_id, geometry (EPSG:4326)."""
    frames = []
    for kml in sorted(Path(kml_dir).glob("*.kml")):
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
        g["plot_id"] = assign_plot_ids(g["Name"])
        g["inventory_file"] = kml.stem
        frames.append(g[["inventory_file", "plot_id", "geometry"]])
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")


def load_plots_dissolved(kml_dir) -> gpd.GeoDataFrame:
    """Uma geometria por parcela. Como cada feature já é uma parcela com plot_id único,
    o dissolve por (inventory_file, plot_id) é inócuo (grupos de 1) — mantido só para
    garantir a unicidade da chave usada no resto do pipeline."""
    return load_plots(kml_dir).dissolve(by=["inventory_file", "plot_id"]).reset_index()
