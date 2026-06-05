"""
Trains an AGB model directly from LiDAR point clouds.

Pipeline per plot:
  1. Load clipped LAZ file
  2. Local ground estimation: for each point, ground = min z of all points
     within 1 m horizontal radius (cKDTree ball query)
  3. height_above_ground = z - local_ground
  4. Filter: keep only points >= 2 m (remove ground returns)
  5. Subsample to N_PTS canopy points (random draw; pad if fewer)
  6. Sort heights → fixed-length vector (permutation-invariant)
  7. Append total point count as extra feature (captures scan density)
  8. Target: AGB M1 (Mg/ha) from inventory summary

Model: GradientBoostingRegressor (sklearn)
Evaluation: leave-one-site-out CV (each fold = one held-out site) → RMSE, R², rRMSE
  Rationale: plots from the same site share forest structure — random k-fold leaks
  site-level signal. LOSO gives a realistic estimate of generalisation to new sites.
Output:
  data/processed/06_model/model.joblib   — trained on all data
  data/processed/06_model/cv_results.csv — per-fold metrics
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import joblib
import laspy
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import root_mean_squared_error, r2_score

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

ROOT      = Path(__file__).parent.parent
LAZ_DIR   = ROOT / "data/processed/03_clipped_lidar"
SUMMARY   = ROOT / "data/processed/05_biomass/summary.csv"
OUT_DIR   = ROOT / "data/processed/06_model"

N_PTS          = 1024   # canopy points sampled per plot
GROUND_RADIUS  = 1.0    # m — radius for local ground estimation
CANOPY_MIN_H   = 2.0    # m — points below this are considered ground returns
SEED           = 42
N_SPLITS       = 5      # dobras do k-fold (todas as parcelas num pote só, peso 1)
OUTLIER_XY_M   = 200.0  # m — pontos além disto da mediana XY são ruído de recorte

# Alvo em log: AGB é muito assimétrico (cauda longa). Treinar em log1p e prever com
# expm1 estabiliza a cauda; as métricas continuam calculadas em Mg/ha (escala original).
Y_FWD = np.log1p
Y_INV = np.expm1


def drop_xy_outliers(x: np.ndarray, y: np.ndarray, z: np.ndarray,
                     max_dist: float = OUTLIER_XY_M):
    """Remove pontos espúrios do recorte (ex.: retornos em zona/origem UTM errada).
    Mantém só pontos a <= max_dist da mediana XY. Conserta parcelas cuja extensão
    estoura para centenas de km por causa de alguns pontos fora do lugar — sem
    descartar a parcela inteira. Devolve a nuvem intacta se não houver o que filtrar."""
    cx, cy = np.median(x), np.median(y)
    keep = (np.abs(x - cx) <= max_dist) & (np.abs(y - cy) <= max_dist)
    if keep.sum() < 10 or keep.all():
        return x, y, z
    return x[keep], y[keep], z[keep]

# Hiperparâmetros do modelo (fonte única — usados no CV, no modelo final e no JSON
# de métricas que a página de Modelos do app lê).
GBR_PARAMS = dict(n_estimators=300, max_depth=4, learning_rate=0.05,
                  subsample=0.8, random_state=SEED)


def local_ground_normalize(x: np.ndarray, y: np.ndarray,
                           z: np.ndarray, cell_size: float) -> np.ndarray:
    """
    Estimates ground using a grid of `cell_size` × `cell_size` metres.
    Each point's ground level = minimum z of all points in the same cell.
    Memory-efficient O(n) alternative to ball-query — equivalent to a
    ~cell_size radius local minimum.
    x, y must be float64 to preserve sub-metre precision in UTM coordinates.
    """
    col = ((x - x.min()) / cell_size).astype(np.int32)
    row = ((y - y.min()) / cell_size).astype(np.int32)

    grid = np.full((row.max() + 1, col.max() + 1), np.inf, dtype=np.float32)
    np.minimum.at(grid, (row, col), z)

    ground = grid[row, col]
    return z - ground


def load_canopy_heights(laz_path: Path, n: int,
                        rng: np.random.Generator) -> tuple[np.ndarray, int] | None:
    """
    Returns (sorted_height_vector_of_length_n, total_point_count), or None.
    Heights are normalized using local 1-m ground estimation; ground returns
    (< CANOPY_MIN_H) are removed before sampling.
    """
    try:
        las = laspy.read(laz_path)
        x = np.array(las.x, dtype=np.float64)
        y = np.array(las.y, dtype=np.float64)
        z = np.array(las.z, dtype=np.float32)
    except Exception as e:
        log.warning(f"  [SKIP] {laz_path.name}: {e}")
        return None

    if len(z) < 10:
        return None

    x, y, z = drop_xy_outliers(x, y, z)

    # Sanity check: plot extent should be < 1 km
    x_range = x.max() - x.min()
    y_range = y.max() - y.min()
    if x_range > 1000 or y_range > 1000:
        log.warning(f"  [SKIP] {laz_path.name}: extent implausível "
                    f"({x_range:.0f}×{y_range:.0f} m)")
        return None

    hag = local_ground_normalize(x, y, z, GROUND_RADIUS)
    total_pts = len(hag)

    canopy = hag[hag >= CANOPY_MIN_H]
    if len(canopy) == 0:
        canopy = hag  # fallback: no filtering if nothing survives

    if len(canopy) >= n:
        idx = rng.choice(len(canopy), size=n, replace=False)
        canopy = canopy[idx]
    else:
        canopy = np.concatenate([canopy,
                                 np.zeros(n - len(canopy), dtype=np.float32)])

    return np.sort(canopy), total_pts


def build_dataset() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Returns X, y, site_groups (for LOSO CV), labels."""
    df = pd.read_csv(SUMMARY)
    df = df[df["agb_m1_Mg_ha"].notna()].copy()

    rng = np.random.default_rng(SEED)
    X_rows, y_rows, groups, labels = [], [], [], []

    for _, row in df.iterrows():
        site = row["site"]
        pid  = str(row["plot_id"])
        laz  = LAZ_DIR / site / f"plot_{pid}.laz"
        if not laz.exists():
            log.warning(f"  [MISS] {site}/plot_{pid}.laz")
            continue

        result = load_canopy_heights(laz, N_PTS, rng)
        if result is None:
            continue

        heights, total_pts = result
        feat = np.append(heights, np.log1p(total_pts).astype(np.float32))
        X_rows.append(feat)
        y_rows.append(row["agb_m1_Mg_ha"])
        groups.append(site)
        labels.append(f"{site}|{pid}")

    log.info(f"  {len(X_rows)} plots  |  {len(set(groups))} sites")
    return (np.stack(X_rows), np.array(y_rows, dtype=np.float32),
            np.array(groups), labels)


def evaluate_cv(X: np.ndarray, y: np.ndarray) -> tuple[pd.DataFrame, dict]:
    """K-fold aleatório sobre TODAS as parcelas (peso 1 cada, sem distinção de site).
    A métrica global agrupa as previsões de todas as dobras (cada parcela conta 1 vez)."""
    kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    all_te, all_pred, records = [], [], []
    for i, (tr, te) in enumerate(kf.split(X), 1):
        model = GradientBoostingRegressor(**GBR_PARAMS)
        model.fit(X[tr], Y_FWD(y[tr]))
        pred = Y_INV(model.predict(X[te]))
        rmse  = root_mean_squared_error(y[te], pred)
        r2    = r2_score(y[te], pred)
        rrmse = rmse / y[te].mean() * 100
        all_te.extend(y[te]); all_pred.extend(pred)
        records.append({"fold": i, "n_test": len(te),
                        "rmse": round(rmse, 2), "r2": round(r2, 4),
                        "rrmse_pct": round(rrmse, 2)})
        log.info(f"  fold {i}  n={len(te):>3}  RMSE={rmse:.1f}  R²={r2:.3f}")

    overall_rmse = root_mean_squared_error(all_te, all_pred)
    overall_r2   = r2_score(all_te, all_pred)
    overall_rrmse = overall_rmse / np.mean(all_te) * 100
    log.info(f"\n  Global ({N_SPLITS}-fold) — RMSE={overall_rmse:.1f}  "
             f"R²={overall_r2:.3f}  rRMSE={overall_rrmse:.1f}%")
    global_metrics = {"rmse": round(float(overall_rmse), 2),
                      "r2": round(float(overall_r2), 4),
                      "rrmse_pct": round(float(overall_rrmse), 2)}
    return pd.DataFrame(records), global_metrics


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info(f"Carregando nuvens de pontos "
             f"(N={N_PTS} pts, ground_radius={GROUND_RADIUS}m, "
             f"canopy_min={CANOPY_MIN_H}m)...")
    X, y, groups, labels = build_dataset()
    log.info(f"  Features por plot: {X.shape[1]} ({N_PTS} alturas + 1 densidade)")
    log.info(f"  AGB M1 — média: {y.mean():.1f}  std: {y.std():.1f}  [Mg/ha]")

    log.info(f"\nValidação cruzada (k-fold aleatório, {N_SPLITS} dobras, peso 1/parcela):")
    cv, global_metrics = evaluate_cv(X, y)
    cv.to_csv(OUT_DIR / "cv_results.csv", index=False)
    log.info(f"\n  Média das dobras — RMSE={cv.rmse.mean():.1f}  "
             f"R²={cv.r2.mean():.3f}  rRMSE={cv.rrmse_pct.mean():.1f}%")

    log.info("\nTreinando modelo final (todos os plots)...")
    final = GradientBoostingRegressor(**GBR_PARAMS)
    final.fit(X, Y_FWD(y))
    joblib.dump({"model": final, "n_pts": N_PTS, "labels": labels},
                OUT_DIR / "model.joblib")
    log.info(f"  Salvo em {OUT_DIR / 'model.joblib'}")

    # Resumo legível pelo app (página de Modelos) — fonte única de hiperparâmetros e
    # métricas globais. cv_results.csv tem o detalhe por site.
    metrics = {
        "key": "gbr",
        "name": "GBR — alturas ordenadas",
        "model": "GradientBoostingRegressor",
        "library": "scikit-learn",
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "target": "agb_m1_Mg_ha",
        "cv_file": "cv_results.csv",
        "approach_key": "model_approach",
        "n_plots": int(X.shape[0]),
        "n_sites": int(len(set(groups))),
        "n_features": int(X.shape[1]),
        "agb_mean": round(float(y.mean()), 1),
        "agb_std": round(float(y.std()), 1),
        "cv": f"K-fold aleatório ({N_SPLITS} dobras, peso 1/parcela)",
        "hyperparameters": GBR_PARAMS,
        "preprocessing": {
            "n_points": N_PTS,
            "ground_radius_m": GROUND_RADIUS,
            "canopy_min_h_m": CANOPY_MIN_H,
            "target_transform": "log1p",
            "feature": "vetor de alturas do dossel ordenadas + log(nº de pontos)",
        },
        "cv_global": global_metrics,
        "cv_fold_mean": {
            "rmse": round(float(cv.rmse.mean()), 2),
            "r2": round(float(cv.r2.mean()), 4),
            "rrmse_pct": round(float(cv.rrmse_pct.mean()), 2),
        },
    }
    (OUT_DIR / "model_metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    log.info(f"  Métricas em {OUT_DIR / 'model_metrics.json'}")


if __name__ == "__main__":
    main()
