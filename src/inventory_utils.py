"""Utilitários compartilhados entre prepare_inventory.py e calculate_biomass.py.

Duas correções estruturais, cada uma resolvendo um problema que afetava treino E
visualização ao mesmo tempo (por isso vivem aqui, não duplicadas nos dois módulos):

1. `fill_nearest_year` — escolha de valor por ÁRVORE, não por SITE. O pipeline
   anterior escolhia uma única coluna de ano (ex.: `dbh_2015`) pro site inteiro, a
   mais próxima do ano do voo LiDAR. Uma árvore medida só em 2018 (ou morta antes de
   2015) ficava sem DBH mesmo tendo dado em outro censo — 14,8% das árvores do
   pipeline caíam nesse buraco, 99,8% delas recuperáveis. Esta função resolve coluna
   por LINHA: para cada árvore, percorre as colunas `{prefix}_<ano>` em ordem de
   proximidade ao ano do LiDAR e usa o primeiro valor válido que aquela árvore tiver.

2. `resolve_utm_zone` — zona UTM real das tiles LiDAR pareadas ao site, não
   recalculada a partir da longitude do centroide do KML. A fórmula
   `int((lon+180)/6)+1` erra perto de fronteira de zona: o site DUC_A01 fica a
   ~0,06° da fronteira 20/21S, a fórmula devolve 21, mas as tiles LiDAR da missão
   foram processadas em 20S (fixo pro projeto todo) — um erro de uma zona inteira
   (~667 km) nas coordenadas de árvore exibidas sobre a nuvem de pontos.
"""

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
INTERSECTIONS_CSV = ROOT / "data/processed/02_intersections/lidar_inventory_intersections.csv"


def _find_lidar_dir() -> Path | None:
    candidates = sorted((ROOT / "data/raw/lidar").glob("LiDAR_Forest_Inventory_Brazil_*"))
    return candidates[0] if candidates else None


def fill_nearest_year(df: pd.DataFrame, prefix: str, lidar_year,
                      positive: bool = False) -> tuple[pd.Series, pd.Series]:
    """Para cada linha, pega o valor de `{prefix}_<ano>` cujo ano está mais próximo
    de `lidar_year` E que tem dado válido NAQUELA linha especificamente — não a
    mesma coluna pro dataframe inteiro. Cai pra coluna sem sufixo (`prefix`, se
    existir) como última prioridade, com o mesmo peso de "ano desconhecido".

    `positive=True` exige valor numérico > 0 (DBH/altura); caso contrário só exige
    não-nulo (usado para campos categóricos como `type`/`dead`).

    Retorna (valores, nome_da_coluna_de_origem_por_linha) — a segunda série serve de
    auditoria (quantas árvores vieram de qual ano).
    """
    import re
    year_cols = [c for c in df.columns if re.fullmatch(rf"{re.escape(prefix)}_\d{{4}}", c)]
    if pd.notna(lidar_year):
        year_cols = sorted(year_cols, key=lambda c: abs(int(c.split("_")[-1]) - int(lidar_year)))
    else:
        year_cols = sorted(year_cols, reverse=True)  # sem ano do LiDAR: ano mais recente primeiro
    bare = [prefix] if prefix in df.columns else []

    out = pd.Series(np.nan, index=df.index, dtype=object)
    src = pd.Series(pd.NA, index=df.index, dtype=object)
    filled = pd.Series(False, index=df.index)

    for col in year_cols + bare:
        if positive:
            vals = pd.to_numeric(df[col], errors="coerce")
            ok = vals.notna() & (vals > 0) & ~filled
        else:
            vals = df[col]
            ok = vals.notna() & (vals.astype(str).str.strip() != "") & ~filled
        if ok.any():
            out[ok] = vals[ok]
            src[ok] = col
            filled |= ok

    return (pd.to_numeric(out, errors="coerce") if positive else out), src


@lru_cache(maxsize=1)
def _site_tile_zones() -> dict:
    """{inventory_file: zona_utm_mais_comum} a partir das tiles LiDAR de fato
    pareadas a cada site (ground truth), não da longitude do centroide do KML."""
    if not INTERSECTIONS_CSV.exists():
        return {}
    lidar_dir = _find_lidar_dir()
    if lidar_dir is None:
        return {}
    tile_csv = lidar_dir / "cms_brazil_lidar_tile_inventory.csv"
    if not tile_csv.exists():
        return {}
    inter = pd.read_csv(INTERSECTIONS_CSV)
    meta = pd.read_csv(tile_csv).set_index("filename")["utmzone"]
    inter = inter.assign(utmzone=inter["laz_file"].map(meta))
    return (inter.dropna(subset=["utmzone"])
            .groupby("inventory_file")["utmzone"]
            .agg(lambda s: s.value_counts().idxmax())
            .to_dict())


def resolve_utm_zone(site_key: str, fallback_lon: float | None = None,
                     fallback_lat: float | None = None) -> str:
    """Zona UTM (ex.: '20S') real das tiles LiDAR pareadas a `site_key`. Cai para a
    fórmula de longitude só quando o site não tem nenhuma tile pareada ainda
    (ex.: chamado antes da etapa de interseção) — nesse caso usa `fallback_lon`."""
    zone = _site_tile_zones().get(site_key)
    if zone:
        return zone
    if fallback_lon is None:
        raise ValueError(f"Zona UTM desconhecida para {site_key!r} e sem fallback_lon.")
    n = int((fallback_lon + 180) / 6) + 1
    hemi = "S" if (fallback_lat or 0) < 0 else "N"
    return f"{n}{hemi}"


def utm_proj_from_zone(zone: str) -> str:
    """'20S' -> string proj4 UTM (datum WGS84/GRS80, consistente com clip_lidar_to_plots)."""
    n = int(zone[:-1])
    south = "+south" if zone[-1].upper() == "S" else ""
    return f"+proj=utm +zone={n} {south} +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs"
