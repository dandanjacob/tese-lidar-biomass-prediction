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

import logging
from pathlib import Path

import joblib
import laspy
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import LeaveOneGroupOut
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


def evaluate_cv(X: np.ndarray, y: np.ndarray, groups: np.ndarray) -> pd.DataFrame:
    logo = LeaveOneGroupOut()
    all_te, all_pred = [], []
    records = []
    for tr, te in logo.split(X, y, groups):
        site = groups[te[0]]
        model = GradientBoostingRegressor(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, random_state=SEED
        )
        model.fit(X[tr], y[tr])
        pred = model.predict(X[te])
        rmse  = root_mean_squared_error(y[te], pred)
        r2    = r2_score(y[te], pred) if len(te) > 1 else float("nan")
        rrmse = rmse / y[te].mean() * 100
        all_te.extend(y[te]); all_pred.extend(pred)
        records.append({"site": site, "n_test": len(te),
                        "rmse": round(rmse, 2), "r2": round(r2, 4),
                        "rrmse_pct": round(rrmse, 2)})
        log.info(f"  {site:<45} n={len(te):>3}  "
                 f"RMSE={rmse:.1f}  R²={r2:.3f}")

    overall_rmse = root_mean_squared_error(all_te, all_pred)
    overall_r2   = r2_score(all_te, all_pred)
    log.info(f"\n  LOSO global — RMSE={overall_rmse:.1f}  R²={overall_r2:.3f}  "
             f"rRMSE={overall_rmse/np.mean(all_te)*100:.1f}%")
    return pd.DataFrame(records)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info(f"Carregando nuvens de pontos "
             f"(N={N_PTS} pts, ground_radius={GROUND_RADIUS}m, "
             f"canopy_min={CANOPY_MIN_H}m)...")
    X, y, groups, labels = build_dataset()
    log.info(f"  Features por plot: {X.shape[1]} ({N_PTS} alturas + 1 densidade)")
    log.info(f"  AGB M1 — média: {y.mean():.1f}  std: {y.std():.1f}  [Mg/ha]")

    log.info("\nValidação cruzada (leave-one-site-out):")
    cv = evaluate_cv(X, y, groups)
    cv.to_csv(OUT_DIR / "cv_results.csv", index=False)
    log.info(f"\n  Média CV — RMSE={cv.rmse.mean():.1f}  "
             f"R²={cv.r2.mean():.3f}  rRMSE={cv.rrmse_pct.mean():.1f}%")

    log.info("\nTreinando modelo final (todos os plots)...")
    final = GradientBoostingRegressor(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, random_state=SEED
    )
    final.fit(X, y)
    joblib.dump({"model": final, "n_pts": N_PTS, "labels": labels},
                OUT_DIR / "model.joblib")
    log.info(f"  Salvo em {OUT_DIR / 'model.joblib'}")


if __name__ == "__main__":
    main()
