"""GBR sobre K quantis de altura — sweep de redução de dimensionalidade.

Mesma abordagem do `train_model.py` (GBR, mesmos hiperparâmetros, mesma CV), mas
em vez das 1024 alturas amostradas e ordenadas, cada parcela vira **K quantis
igualmente espaçados** da distribuição de altura do dossel (determinístico, sem
ruído de amostragem) + `log(nº de pontos)`. K vem da env `GBR_HEIGHTS_K`.

Roda nas duas variantes (full / no-outliers) via `EXCLUDE_OUTLIERS=1`, como os demais.
Objetivo: medir CV R² × nº de alturas e ver quanto da dimensionalidade é só overfitting.
"""
import json
import os
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import laspy

from train_model import (
    log, SEED, N_SPLITS, GROUND_RADIUS, CANOPY_MIN_H, GBR_PARAMS,
    LAZ_DIR, SUMMARY, OUT_DIR, Y_FWD, Y_INV,
    xy_inlier_mask, height_above_ground, evaluate_cv,
)
from outlier_filter import filter_summary, SUFFIX, VARIANT
from train_eval import save_oof, save_lc, learning_curve
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import root_mean_squared_error, r2_score

K = int(os.environ.get("GBR_HEIGHTS_K", "32"))   # nº de quantis de altura


def load_canopy_quantiles(laz_path, k):
    """K quantis igualmente espaçados das alturas de dossel + total de pontos.

    Determinístico: usa TODOS os pontos de dossel (sem subamostragem aleatória)."""
    try:
        las = laspy.read(laz_path)
        x = np.array(las.x, dtype=np.float64)
        y = np.array(las.y, dtype=np.float64)
        z = np.array(las.z, dtype=np.float32)
        cls = np.array(las.classification, dtype=np.uint8)
    except Exception as e:
        log.warning(f"  [SKIP] {laz_path.name}: {e}")
        return None
    if len(z) < 10:
        return None

    keep = xy_inlier_mask(x, y)
    x, y, z, cls = x[keep], y[keep], z[keep], cls[keep]
    if x.max() - x.min() > 1000 or y.max() - y.min() > 1000:
        log.warning(f"  [SKIP] {laz_path.name}: extent implausível")
        return None

    hag = height_above_ground(x, y, z, cls, GROUND_RADIUS)
    total_pts = len(hag)
    canopy = hag[hag >= CANOPY_MIN_H]
    if len(canopy) == 0:
        canopy = hag

    qs = np.quantile(canopy, np.linspace(0.0, 1.0, k)).astype(np.float32)
    return qs, total_pts


def build_dataset():
    """X (K quantis + log densidade), y, sites, labels."""
    df = filter_summary(pd.read_csv(SUMMARY))
    df = df[df["agb_m1_Mg_ha"].notna()].copy()

    X_rows, y_rows, groups, labels = [], [], [], []
    for _, row in df.iterrows():
        site = row["site"]
        pid = str(row["plot_id"])
        laz = LAZ_DIR / site / f"plot_{pid}.laz"
        if not laz.exists():
            log.warning(f"  [MISS] {site}/plot_{pid}.laz")
            continue
        result = load_canopy_quantiles(laz, K)
        if result is None:
            continue
        qs, total_pts = result
        feat = np.append(qs, np.log1p(total_pts).astype(np.float32))
        X_rows.append(feat)
        y_rows.append(row["agb_m1_Mg_ha"])
        groups.append(site)
        labels.append(f"{site}|{pid}")

    log.info(f"  {len(X_rows)} plots  |  {len(set(groups))} sites")
    return (np.stack(X_rows), np.array(y_rows, dtype=np.float32),
            np.array(groups), labels)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log.info(f"GBR — {K} quantis de altura  (variante: {VARIANT})")
    X, y, groups, labels = build_dataset()
    log.info(f"  Features por plot: {X.shape[1]} ({K} quantis + 1 densidade)")
    log.info(f"  AGB M1 — média: {y.mean():.1f}  std: {y.std():.1f}  [Mg/ha]")

    tag = f"gbrh{K}{SUFFIX}"
    log.info(f"\nValidação cruzada (k-fold aleatório, {N_SPLITS} dobras, peso 1/parcela):")
    cv, global_metrics, (oof_t, oof_p, oof_i) = evaluate_cv(X, y)
    cv.to_csv(OUT_DIR / f"cv_results_{tag}.csv", index=False)
    save_oof(OUT_DIR / f"oof_{tag}.json", oof_t, oof_p, np.array(labels)[oof_i])
    sizes, rmses_lc = learning_curve(len(X), SEED, lambda tr, te: root_mean_squared_error(
        y[te], Y_INV(GradientBoostingRegressor(**GBR_PARAMS).fit(X[tr], Y_FWD(y[tr])).predict(X[te]))))
    save_lc(OUT_DIR / f"lc_{tag}.json", sizes, rmses_lc)

    log.info("\nTreinando modelo final (todas as parcelas)...")
    final = GradientBoostingRegressor(**GBR_PARAMS)
    final.fit(X, Y_FWD(y))
    joblib.dump({"model": final, "k_quantis": K, "labels": labels},
                OUT_DIR / f"model_{tag}.joblib")

    preds = [Y_INV(p) for p in final.staged_predict(X)]
    rmses = [round(float(root_mean_squared_error(y, p)), 3) for p in preds]
    r2s = [round(float(r2_score(y, p)), 4) for p in preds]
    (OUT_DIR / f"history_{tag}.json").write_text(json.dumps({
        "x": list(range(1, len(rmses) + 1)), "rmse": rmses, "r2": r2s,
        "x_kind": "iteration"}, ensure_ascii=False))

    metrics = {
        "key": tag,
        "name": f"GBR — {K} quantis",
        "model": "GradientBoostingRegressor",
        "library": "scikit-learn",
        "variant": VARIANT,
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "target": "agb_m1_Mg_ha",
        "cv_file": f"cv_results_{tag}.csv",
        "approach_key": "gbrh_approach",
        "n_plots": int(X.shape[0]),
        "n_sites": int(len(set(groups))),
        "n_features": int(X.shape[1]),
        "agb_mean": round(float(y.mean()), 1),
        "agb_std": round(float(y.std()), 1),
        "cv": f"K-fold aleatório ({N_SPLITS} dobras, peso 1/parcela)",
        "hyperparameters": GBR_PARAMS,
        "preprocessing": {
            "k_quantis": K,
            "ground_radius_m": GROUND_RADIUS,
            "canopy_min_h_m": CANOPY_MIN_H,
            "target_transform": "log1p",
            "feature": f"{K} quantis igualmente espaçados das alturas de dossel + log(nº de pontos)",
        },
        "cv_global": global_metrics,
        "cv_fold_mean": {
            "rmse": round(float(cv.rmse.mean()), 2),
            "r2": round(float(cv.r2.mean()), 4),
            "rrmse_pct": round(float(cv.rrmse_pct.mean()), 2),
        },
    }
    (OUT_DIR / f"model_metrics_{tag}.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    log.info(f"  Métricas em {OUT_DIR / f'model_metrics_{tag}.json'}  "
             f"(CV R²={global_metrics['r2']}  RMSE={global_metrics['rmse']})")


if __name__ == "__main__":
    main()
