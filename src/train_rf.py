"""
Treina um modelo de AGB com RANDOM FOREST sobre as MESMAS 37 métricas estruturais
da abordagem ABA (ver train_aba.py). Serve para comparar, sobre exatamente as mesmas
features, um ensemble de árvores por bagging (RandomForest) contra o boosting (GBR).

Reaproveita a extração de features do train_aba (build_dataset) — então qualquer
mudança nas métricas vale para os dois modelos. Avaliação idêntica: k-fold aleatório
sobre todas as parcelas (peso 1 cada, sem distinção de site), alvo em log1p.

Saídas:
  data/processed/06_model/model_rf.joblib
  data/processed/06_model/cv_results_rf.csv
  data/processed/06_model/model_metrics_rf.json
"""

import json
import logging
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import root_mean_squared_error, r2_score

from train_model import OUT_DIR, SEED, N_SPLITS, Y_FWD, Y_INV
from train_aba import build_dataset, CELL, GROUND_RADIUS, CANOPY_MIN_H
from outlier_filter import SUFFIX, VARIANT

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# Bagging de árvores fundas e descorrelacionadas — bom baseline robusto e sem ajuste fino.
RF_PARAMS = dict(n_estimators=500, max_depth=None, min_samples_leaf=3,
                 max_features=0.5, random_state=SEED, n_jobs=-1)


def evaluate_cv(X, y) -> tuple[pd.DataFrame, dict]:
    kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    all_te, all_pred, records = [], [], []
    for i, (tr, te) in enumerate(kf.split(X), 1):
        model = RandomForestRegressor(**RF_PARAMS)
        model.fit(X[tr], Y_FWD(y[tr]))
        pred = Y_INV(model.predict(X[te]))
        rmse  = root_mean_squared_error(y[te], pred)
        r2    = r2_score(y[te], pred)
        rrmse = rmse / y[te].mean() * 100
        all_te.extend(y[te]); all_pred.extend(pred)
        records.append({"fold": i, "n_test": len(te), "rmse": round(rmse, 2),
                        "r2": round(r2, 4), "rrmse_pct": round(rrmse, 2)})
        log.info(f"  fold {i}  n={len(te):>3}  RMSE={rmse:.1f}  R²={r2:.3f}")

    g_rmse = root_mean_squared_error(all_te, all_pred)
    g_r2   = r2_score(all_te, all_pred)
    g_rrmse = g_rmse / np.mean(all_te) * 100
    log.info(f"\n  Global ({N_SPLITS}-fold) — RMSE={g_rmse:.1f}  R²={g_r2:.3f}  "
             f"rRMSE={g_rrmse:.1f}%")
    return pd.DataFrame(records), {"rmse": round(float(g_rmse), 2),
                                   "r2": round(float(g_r2), 4),
                                   "rrmse_pct": round(float(g_rrmse), 2)}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Extraindo métricas ABA (mesmas features do GBR-ABA)...")
    X, y, groups, labels, feat_names = build_dataset()
    log.info(f"  AGB M1 — média {y.mean():.1f} std {y.std():.1f} [Mg/ha]")

    log.info(f"\nValidação cruzada (k-fold aleatório, {N_SPLITS} dobras, peso 1/parcela):")
    cv, g = evaluate_cv(X, y)
    cv.to_csv(OUT_DIR / f"cv_results_rf{SUFFIX}.csv", index=False)
    log.info(f"\n  Média das dobras — RMSE={cv.rmse.mean():.1f}  R²={cv.r2.mean():.3f}  "
             f"rRMSE={cv.rrmse_pct.mean():.1f}%")

    log.info("\nTreinando modelo final (todas as parcelas)...")
    final = RandomForestRegressor(**RF_PARAMS)
    final.fit(X, Y_FWD(y))
    joblib.dump({"model": final, "feature_names": feat_names, "labels": labels},
                OUT_DIR / f"model_rf{SUFFIX}.joblib")

    # Histórico de treino: RMSE (Mg/ha) no treino conforme a floresta cresce. RF não tem
    # "épocas"; usa-se a média acumulada das predições das primeiras k árvores.
    tree_preds = np.array([est.predict(X) for est in final.estimators_])  # log space
    cum = np.cumsum(tree_preds, axis=0) / np.arange(1, len(tree_preds) + 1)[:, None]
    step = max(1, len(tree_preds) // 100)
    xs = list(range(step, len(tree_preds) + 1, step))
    ys = [round(float(root_mean_squared_error(y, Y_INV(cum[i - 1]))), 3) for i in xs]
    (OUT_DIR / f"history_rf{SUFFIX}.json").write_text(json.dumps({
        "x": xs, "y": ys, "x_kind": "trees", "y_kind": "rmse"}, ensure_ascii=False))

    imp = sorted(zip(feat_names, final.feature_importances_),
                 key=lambda t: t[1], reverse=True)
    log.info("\n  Features mais importantes:")
    for name, val in imp[:15]:
        log.info(f"    {name:<18} {val:.3f}")

    metrics = {
        "key": f"rf{SUFFIX}",
        "name": "Random Forest — métricas estruturais (ABA)",
        "model": "RandomForestRegressor",
        "library": "scikit-learn",
        "variant": VARIANT,
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "target": "agb_m1_Mg_ha",
        "cv_file": f"cv_results_rf{SUFFIX}.csv",
        "approach_key": "model_approach_rf",
        "n_plots": int(X.shape[0]),
        "n_sites": int(len(set(groups))),
        "n_features": int(X.shape[1]),
        "agb_mean": round(float(y.mean()), 1),
        "agb_std": round(float(y.std()), 1),
        "cv": f"K-fold aleatório ({N_SPLITS} dobras, peso 1/parcela)",
        "hyperparameters": RF_PARAMS,
        "preprocessing": {
            "cell_size_m": CELL,
            "ground_radius_m": GROUND_RADIUS,
            "canopy_min_h_m": CANOPY_MIN_H,
            "target_transform": "log1p",
            "feature_families": "altura · densidade vertical · convolucionais (CHM)",
            "feature_names": feat_names,
        },
        "feature_importance": [{"feature": n, "importance": round(float(v), 4)}
                               for n, v in imp],
        "cv_global": g,
        "cv_fold_mean": {"rmse": round(float(cv.rmse.mean()), 2),
                         "r2": round(float(cv.r2.mean()), 4),
                         "rrmse_pct": round(float(cv.rrmse_pct.mean()), 2)},
    }
    (OUT_DIR / f"model_metrics_rf{SUFFIX}.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False))
    log.info(f"\n  Salvo: model_rf{SUFFIX}.joblib · cv_results_rf{SUFFIX}.csv · "
             f"model_metrics_rf{SUFFIX}.json")


if __name__ == "__main__":
    main()
