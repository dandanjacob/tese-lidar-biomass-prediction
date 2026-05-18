"""
Trains an AGB model directly from LiDAR point clouds.

Pipeline per plot:
  1. Load clipped LAZ file
  2. Extract z values; subtract per-plot minimum → height above ground (m)
  3. Subsample to N_PTS points (random draw; pad with zeros if fewer)
  4. Sort heights → fixed-length vector (permutation-invariant, no hand-crafted features)
  5. Target: AGB M1 (Mg/ha) from inventory summary

Model: GradientBoostingRegressor (sklearn)
Evaluation: 5-fold cross-validation → RMSE, R², rRMSE
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
from sklearn.model_selection import KFold
from sklearn.metrics import root_mean_squared_error, r2_score

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

ROOT      = Path(__file__).parent.parent
LAZ_DIR   = ROOT / "data/processed/03_clipped_lidar"
SUMMARY   = ROOT / "data/processed/05_biomass/summary.csv"
OUT_DIR   = ROOT / "data/processed/06_model"

N_PTS     = 512   # points sampled per plot
SEED      = 42


def load_heights(laz_path: Path, n: int, rng: np.random.Generator) -> np.ndarray | None:
    """Returns sorted height-above-ground vector of length n, or None on failure."""
    try:
        las = laspy.read(laz_path)
        z = np.array(las.z, dtype=np.float32)
    except Exception as e:
        log.warning(f"  [SKIP] {laz_path.name}: {e}")
        return None

    if len(z) == 0:
        return None

    z -= z.min()  # height above ground (approx.)

    if len(z) >= n:
        idx = rng.choice(len(z), size=n, replace=False)
        z = z[idx]
    else:
        # pad with zeros (ground level) when plot has fewer points
        z = np.concatenate([z, np.zeros(n - len(z), dtype=np.float32)])

    return np.sort(z)


def build_dataset() -> tuple[np.ndarray, np.ndarray, list[str]]:
    df = pd.read_csv(SUMMARY)
    df = df[df["agb_m1_Mg_ha"].notna()].copy()

    rng = np.random.default_rng(SEED)
    X_rows, y_rows, labels = [], [], []

    for _, row in df.iterrows():
        site = row["site"]
        pid  = str(row["plot_id"])
        laz  = LAZ_DIR / site / f"plot_{pid}.laz"
        if not laz.exists():
            log.warning(f"  [MISS] {site}/plot_{pid}.laz")
            continue

        heights = load_heights(laz, N_PTS, rng)
        if heights is None:
            continue

        X_rows.append(heights)
        y_rows.append(row["agb_m1_Mg_ha"])
        labels.append(f"{site}|{pid}")

    return np.stack(X_rows), np.array(y_rows, dtype=np.float32), labels


def evaluate_cv(X: np.ndarray, y: np.ndarray) -> pd.DataFrame:
    kf = KFold(n_splits=5, shuffle=True, random_state=SEED)
    records = []
    for fold, (tr, te) in enumerate(kf.split(X), 1):
        model = GradientBoostingRegressor(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            subsample=0.8, random_state=SEED
        )
        model.fit(X[tr], y[tr])
        pred = model.predict(X[te])
        rmse  = root_mean_squared_error(y[te], pred)
        r2    = r2_score(y[te], pred)
        rrmse = rmse / y[te].mean() * 100
        records.append({"fold": fold, "n_test": len(te),
                        "rmse": round(rmse, 2), "r2": round(r2, 4),
                        "rrmse_pct": round(rrmse, 2)})
        log.info(f"  Fold {fold}: RMSE={rmse:.1f}  R²={r2:.3f}  rRMSE={rrmse:.1f}%")
    return pd.DataFrame(records)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info(f"Carregando nuvens de pontos (N={N_PTS} pts/plot)...")
    X, y, labels = build_dataset()
    log.info(f"  Dataset: {len(y)} plots  |  features: {X.shape[1]}")
    log.info(f"  AGB M1 — média: {y.mean():.1f}  std: {y.std():.1f}  [Mg/ha]")

    log.info("\nValidação cruzada (5-fold):")
    cv = evaluate_cv(X, y)
    cv.to_csv(OUT_DIR / "cv_results.csv", index=False)

    log.info(f"\n  Média CV — RMSE={cv.rmse.mean():.1f}  R²={cv.r2.mean():.3f}  rRMSE={cv.rrmse_pct.mean():.1f}%")

    log.info("\nTreinando modelo final (todos os plots)...")
    final = GradientBoostingRegressor(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, random_state=SEED
    )
    final.fit(X, y)
    joblib.dump({"model": final, "n_pts": N_PTS, "labels": labels},
                OUT_DIR / "model.joblib")
    log.info(f"  Salvo em {OUT_DIR / 'model.joblib'}")


if __name__ == "__main__":
    main()
