"""
Treina um modelo de AGB pela ABORDAGEM POR ÁREA (ABA — Area-Based Approach).

Em vez de jogar a nuvem (crua ou ordenada) no modelo, extrai-se um VETOR DE
MÉTRICAS ESTRUTURAIS interpretáveis por parcela e alimenta-se um GBR. É o padrão
da literatura de LiDAR florestal (FUSION / lidR) e, ao contrário das redes,
permite reportar a IMPORTÂNCIA de cada métrica — útil para a discussão da tese.

Pipeline por parcela (idêntico a train_model.py até a altura sobre o solo):
  1. Carrega LAZ recortado da parcela.
  2. Altura sobre o solo (HAG): solo = mínimo de Z numa grade local; z → z - solo.
  3. Extrai três famílias de métricas (todas sobre HAG):

     A) Distribuição de altura (sobre pontos de dossel, HAG >= CANOPY_MIN_H):
        h_max, h_mean, h_std, h_cv, percentis p05..p99, assimetria, curtose,
        CRR (canopy relief ratio = (média - mín)/(máx - mín)).

     B) Densidade vertical / cobertura (sobre TODOS os pontos):
        cover_2m  — fração de retornos acima de 2 m (proxy de cobertura);
        pz_above_mean — fração acima da altura média;
        D0..D9   — deciles de densidade (proporção de pontos de dossel em cada
                   uma das 10 faixas de altura entre 0 e h_max);
        vfd_entropy — entropia vertical (diversidade de altura da folhagem);
        pt_density — densidade de pontos (pts / m²).

     C) Métricas convolucionais espaciais (sobre um CHM rasterizado, célula 1 m):
        chm_mean, chm_sd (rugosidade), chm_max, chm_range;
        canopy_cover_grid — fração de células preenchidas com altura >= 2 m;
        gap_fraction — fração de células vazias (clareiras);
        lap_roughness — média |Laplaciano 3x3| do CHM (textura/rugosidade local,
                        uma convolução de verdade sobre a grade de altura);
        ptdens_cv — heterogeneidade espacial da densidade de pontos (CV da
                    contagem de pontos por célula).

  4. Alvo: AGB M1 (Mg/ha) do summary de inventário.

Modelo: GradientBoostingRegressor (mesmos hiperparâmetros de train_model.py).
Avaliação: leave-one-site-out (LOSO), igual às demais abordagens, para comparação
justa.
Saídas:
  data/processed/06_model/model_aba.joblib
  data/processed/06_model/cv_results_aba.csv
  data/processed/06_model/model_metrics_aba.json
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

from train_model import (height_above_ground, xy_inlier_mask, LAZ_DIR, SUMMARY,
                         OUT_DIR, GROUND_RADIUS, CANOPY_MIN_H, GBR_PARAMS, SEED,
                         N_SPLITS, Y_FWD, Y_INV)
from outlier_filter import filter_summary, SUFFIX, VARIANT, TARGET
from train_eval import save_oof, save_lc, learning_curve

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

CELL        = 1.0   # m — tamanho da célula do CHM / grade de densidade
PERCENTILES = [5, 10, 25, 50, 75, 90, 95, 99]
N_DECILES   = 10    # faixas de densidade vertical D0..D9
LAP_KERNEL  = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)


def _skew_kurt(v: np.ndarray) -> tuple[float, float]:
    """Assimetria e curtose-excesso (definição de Fisher), sem depender de scipy."""
    m, s = v.mean(), v.std()
    if s < 1e-6:
        return 0.0, 0.0
    z = (v - m) / s
    return float((z ** 3).mean()), float((z ** 4).mean() - 3.0)


def _grid_metrics(x: np.ndarray, y: np.ndarray, hag: np.ndarray) -> dict:
    """Métricas espaciais/convolucionais sobre o CHM (máx. HAG por célula)."""
    col = ((x - x.min()) / CELL).astype(np.int32)
    row = ((y - y.min()) / CELL).astype(np.int32)
    n_rows, n_cols = row.max() + 1, col.max() + 1

    chm   = np.full((n_rows, n_cols), -np.inf, dtype=np.float32)
    count = np.zeros((n_rows, n_cols), dtype=np.int32)
    np.maximum.at(chm, (row, col), hag)
    np.add.at(count, (row, col), 1)

    filled = count > 0
    n_cells = chm.size
    n_filled = int(filled.sum())
    chm_f = chm[filled]

    # Laplaciano 3x3 sobre o CHM (vazios = 0) — textura/rugosidade local do dossel.
    chm0 = np.where(filled, chm, 0.0).astype(np.float32)
    lap = (
        LAP_KERNEL[1, 1] * chm0[1:-1, 1:-1]
        + chm0[:-2, 1:-1] + chm0[2:, 1:-1]
        + chm0[1:-1, :-2] + chm0[1:-1, 2:]
    ) if (n_rows >= 3 and n_cols >= 3) else np.zeros(1, dtype=np.float32)
    interior = filled[1:-1, 1:-1] if (n_rows >= 3 and n_cols >= 3) else np.array([False])
    lap_rough = float(np.abs(lap[interior]).mean()) if interior.any() else 0.0

    cnt_f = count[filled].astype(np.float32)
    plot_area = n_filled * CELL * CELL  # m²

    return {
        "chm_mean":          float(chm_f.mean()),
        "chm_sd":            float(chm_f.std()),
        "chm_max":           float(chm_f.max()),
        "chm_range":         float(chm_f.max() - chm_f.min()),
        "canopy_cover_grid": float((chm_f >= CANOPY_MIN_H).mean()),
        "gap_fraction":      float(1.0 - n_filled / n_cells),
        "lap_roughness":     lap_rough,
        "ptdens_cv":         float(cnt_f.std() / (cnt_f.mean() + 1e-6)),
        "pt_density":        float(len(hag) / (plot_area + 1e-6)),
    }


def extract_features(laz_path: Path) -> dict | None:
    """Vetor de métricas ABA da parcela, ou None se a nuvem for inutilizável."""
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
    if (x.max() - x.min()) > 1000 or (y.max() - y.min()) > 1000:
        log.warning(f"  [SKIP] {laz_path.name}: extensão implausível")
        return None

    hag = height_above_ground(x, y, z, cls, GROUND_RADIUS)
    hag = np.clip(hag, 0.0, None)  # ruído abaixo do solo → 0

    canopy = hag[hag >= CANOPY_MIN_H]
    if len(canopy) < 5:
        canopy = hag  # fallback: parcela muito esparsa / aberta

    f: dict = {}

    # --- A) Distribuição de altura (pontos de dossel) ---
    h_max, h_mean, h_std = canopy.max(), canopy.mean(), canopy.std()
    f["h_max"]  = float(h_max)
    f["h_mean"] = float(h_mean)
    f["h_std"]  = float(h_std)
    f["h_cv"]   = float(h_std / (h_mean + 1e-6))
    for p, v in zip(PERCENTILES, np.percentile(canopy, PERCENTILES)):
        f[f"p{p:02d}"] = float(v)
    f["h_skew"], f["h_kurt"] = _skew_kurt(canopy)
    f["crr"] = float((h_mean - canopy.min()) / (h_max - canopy.min() + 1e-6))

    # --- B) Densidade vertical / cobertura (todos os pontos) ---
    f["cover_2m"]      = float((hag >= CANOPY_MIN_H).mean())
    f["pz_above_mean"] = float((canopy >= h_mean).mean())
    edges = np.linspace(0.0, h_max + 1e-6, N_DECILES + 1)
    dec = np.histogram(canopy, bins=edges)[0].astype(np.float32)
    dec /= dec.sum() + 1e-6
    for i, d in enumerate(dec):
        f[f"D{i}"] = float(d)
    p = dec[dec > 0]
    f["vfd_entropy"] = float(-(p * np.log(p)).sum() / np.log(N_DECILES))

    # --- C) Métricas convolucionais espaciais (CHM) ---
    f.update(_grid_metrics(x, y, hag))

    return f


def build_dataset() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], list[str]]:
    """Retorna X, y, grupos-de-site (LOSO), rótulos das parcelas, nomes das features."""
    df = filter_summary(pd.read_csv(SUMMARY))
    df = df[df[TARGET].notna()].copy()

    rows, y_rows, groups, labels = [], [], [], []
    feat_names: list[str] | None = None

    for _, row in df.iterrows():
        site, pid = row["site"], str(row["plot_id"])
        laz = LAZ_DIR / site / f"plot_{pid}.laz"
        if not laz.exists():
            log.warning(f"  [MISS] {site}/plot_{pid}.laz")
            continue

        feats = extract_features(laz)
        if feats is None:
            continue
        if feat_names is None:
            feat_names = list(feats.keys())

        rows.append([feats[k] for k in feat_names])
        y_rows.append(row[TARGET])
        groups.append(site)
        labels.append(f"{site}|{pid}")

    log.info(f"  {len(rows)} parcelas  |  {len(set(groups))} sites  |  "
             f"{len(feat_names)} features")
    X = np.array(rows, dtype=np.float32)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    return (X, np.array(y_rows, dtype=np.float32),
            np.array(groups), labels, feat_names)


def evaluate_cv(X, y) -> tuple[pd.DataFrame, dict]:
    """K-fold aleatório sobre todas as parcelas (peso 1 cada, sem distinção de site)."""
    kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    all_te, all_pred, all_idx, records = [], [], [], []
    for i, (tr, te) in enumerate(kf.split(X), 1):
        model = GradientBoostingRegressor(**GBR_PARAMS)
        model.fit(X[tr], Y_FWD(y[tr]))
        pred = Y_INV(model.predict(X[te]))
        rmse  = root_mean_squared_error(y[te], pred)
        r2    = r2_score(y[te], pred)
        rrmse = rmse / y[te].mean() * 100
        all_te.extend(y[te]); all_pred.extend(pred); all_idx.extend(te)
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
                                   "rrmse_pct": round(float(g_rrmse), 2)}, (all_te, all_pred, all_idx)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info(f"Extraindo métricas ABA (célula={CELL}m, ground_radius={GROUND_RADIUS}m, "
             f"canopy_min={CANOPY_MIN_H}m)...")
    X, y, groups, labels, feat_names = build_dataset()
    log.info(f"  AGB M1 — média {y.mean():.1f} std {y.std():.1f} [Mg/ha]")

    log.info(f"\nValidação cruzada (k-fold aleatório, {N_SPLITS} dobras, peso 1/parcela):")
    cv, g, (oof_t, oof_p, oof_i) = evaluate_cv(X, y)
    cv.to_csv(OUT_DIR / f"cv_results_aba{SUFFIX}.csv", index=False)
    save_oof(OUT_DIR / f"oof_aba{SUFFIX}.json", oof_t, oof_p, np.array(labels)[oof_i])
    sizes, rmses = learning_curve(len(X), SEED, lambda tr, te: root_mean_squared_error(
        y[te], Y_INV(GradientBoostingRegressor(**GBR_PARAMS).fit(X[tr], Y_FWD(y[tr])).predict(X[te]))))
    save_lc(OUT_DIR / f"lc_aba{SUFFIX}.json", sizes, rmses)
    log.info(f"\n  Média das dobras — RMSE={cv.rmse.mean():.1f}  R²={cv.r2.mean():.3f}  "
             f"rRMSE={cv.rrmse_pct.mean():.1f}%")

    log.info("\nTreinando modelo final (todas as parcelas)...")
    final = GradientBoostingRegressor(**GBR_PARAMS)
    final.fit(X, Y_FWD(y))
    joblib.dump({"model": final, "feature_names": feat_names, "labels": labels},
                OUT_DIR / f"model_aba{SUFFIX}.joblib")

    # Histórico de treino: RMSE (Mg/ha) no conjunto de treino a cada iteração de boosting.
    preds = [Y_INV(p) for p in final.staged_predict(X)]
    rmses = [round(float(root_mean_squared_error(y, p)), 3) for p in preds]
    r2s = [round(float(r2_score(y, p)), 4) for p in preds]
    (OUT_DIR / f"history_aba{SUFFIX}.json").write_text(json.dumps({
        "x": list(range(1, len(rmses) + 1)), "rmse": rmses, "r2": r2s,
        "x_kind": "iteration"}, ensure_ascii=False))

    # Importância das features (vantagem da ABA: modelo interpretável) — top 15.
    imp = sorted(zip(feat_names, final.feature_importances_),
                 key=lambda t: t[1], reverse=True)
    log.info("\n  Features mais importantes:")
    for name, val in imp[:15]:
        log.info(f"    {name:<18} {val:.3f}")

    metrics = {
        "key": f"aba{SUFFIX}",
        "name": "GBR — métricas estruturais (ABA)",
        "model": "GradientBoostingRegressor",
        "library": "scikit-learn",
        "variant": VARIANT,
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "target": TARGET,
        "cv_file": f"cv_results_aba{SUFFIX}.csv",
        "approach_key": "model_approach_aba",
        "n_plots": int(X.shape[0]),
        "n_sites": int(len(set(groups))),
        "n_features": int(X.shape[1]),
        "agb_mean": round(float(y.mean()), 1),
        "agb_std": round(float(y.std()), 1),
        "cv": f"K-fold aleatório ({N_SPLITS} dobras, peso 1/parcela)",
        "hyperparameters": GBR_PARAMS,
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
    (OUT_DIR / f"model_metrics_aba{SUFFIX}.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False))
    log.info(f"\n  Salvo: model_aba{SUFFIX}.joblib · cv_results_aba{SUFFIX}.csv · "
             f"model_metrics_aba{SUFFIX}.json")


if __name__ == "__main__":
    main()
