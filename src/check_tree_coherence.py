"""Varredura de coerência espacial: posição das árvores do inventário (UTM) vs.
a nuvem de pontos LiDAR recortada da mesma parcela.

Motivação: a visualização de nuvem de pontos sobrepõe árvore e LiDAR assumindo que
as duas fontes estão no mesmo referencial métrico. Quando não estão — coordenada em
graus lida como se fosse UTM, zona UTM errada perto de fronteira de zona (ver
inventory_utils.resolve_utm_zone) — a árvore aparece a quilômetros de distância da
nuvem, e a visualização falha silenciosamente (sem erro, só nada bate).

Critério: fração de árvores do site/parcela cuja posição cai dentro da bounding
box da nuvem (+ margem de 20% da extensão, pra não penalizar borda/GPS normal).
Sites com fração baixa entram no relatório para investigação — valores típicos de
erro de GPS sob dossel (alguns a ~20 m) não disparam o alerta; o que dispara é
incoerência de ordem de grandeza (zona/unidade errada).

Saída: data/processed/03_clipped_lidar/tree_coherence_report.csv
Uso: python src/check_tree_coherence.py [--threshold 0.5]
"""

import argparse
import logging
from pathlib import Path

import laspy
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
INV_DIR = ROOT / "data/processed/04_inventory"
LAZ_DIR = ROOT / "data/processed/03_clipped_lidar"
OUT_CSV = LAZ_DIR / "tree_coherence_report.csv"

BBOX_MARGIN_FRAC = 0.2   # margem como fração da extensão da nuvem, pra não penalizar borda


def check_plot(easting: pd.Series, northing: pd.Series, laz_path: Path) -> dict | None:
    try:
        las = laspy.read(laz_path)
    except Exception as e:
        return {"error": f"laz ilegível: {e}"}
    if len(las.x) < 10:
        return None

    bx0, bx1 = float(las.x.min()), float(las.x.max())
    by0, by1 = float(las.y.min()), float(las.y.max())
    mx, my = BBOX_MARGIN_FRAC * (bx1 - bx0), BBOX_MARGIN_FRAC * (by1 - by0)

    inside = ((easting >= bx0 - mx) & (easting <= bx1 + mx) &
              (northing >= by0 - my) & (northing <= by1 + my))
    tree_cx, tree_cy = easting.mean(), northing.mean()
    cloud_cx, cloud_cy = (bx0 + bx1) / 2, (by0 + by1) / 2
    offset = float(np.hypot(tree_cx - cloud_cx, tree_cy - cloud_cy))

    return {
        "n_trees": int(len(easting)),
        "frac_in_bbox": round(float(inside.mean()), 3),
        "offset_m": round(offset, 1),
        "cloud_extent_m": round(max(bx1 - bx0, by1 - by0), 1),
    }


def run(threshold: float) -> pd.DataFrame:
    rows = []
    for csv in sorted(INV_DIR.glob("*.csv")):
        site = csv.stem
        lazdir = LAZ_DIR / site
        if not lazdir.exists():
            continue
        inv = pd.read_csv(csv, low_memory=False)
        if not {"utm_easting", "utm_northing", "plot_id"}.issubset(inv.columns):
            continue
        e_all = pd.to_numeric(inv["utm_easting"], errors="coerce")
        n_all = pd.to_numeric(inv["utm_northing"], errors="coerce")

        for lazf in sorted(lazdir.glob("plot_*.laz")):
            pid = lazf.stem.replace("plot_", "")
            idx = inv.index[inv["plot_id"].astype(str) == pid]
            if len(idx) == 0:
                continue
            e, n = e_all[idx], n_all[idx]
            ok = e.notna() & n.notna()
            if ok.sum() < 3:
                continue
            res = check_plot(e[ok], n[ok], lazf)
            if res is None:
                continue
            res.update(site=site, plot=pid)
            rows.append(res)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False)

    log.info(f"Parcelas avaliadas: {len(df)}")
    bad = df[df.get("frac_in_bbox", 1.0) < threshold] if not df.empty else df
    if bad.empty:
        log.info(f"Nenhuma parcela abaixo do limiar ({threshold:.0%} dentro da nuvem).")
    else:
        log.warning(f"\n{len(bad)} parcelas com <{threshold:.0%} das árvores dentro da nuvem LiDAR "
                    "(incoerência espacial, não erro normal de GPS):")
        for site, sub in bad.groupby("site"):
            log.warning(f"  {site}: {len(sub)} parcelas, offset mediano {sub.offset_m.median():,.0f} m")
    log.info(f"\nRelatório completo: {OUT_CSV}")
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.5,
                    help="Fração mínima de árvores dentro da nuvem antes de soar o alerta (default 0.5)")
    args = ap.parse_args()
    run(args.threshold)
