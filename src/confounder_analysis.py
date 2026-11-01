"""Análise de confundidores (P7) e teste pareado entre modelos (P8) — auditoria
científica da tese.

P7 — Confundidor de campanha e densidade de varredura (artigo_discussao.md §4.5):
  (a) R² do ABA (melhor variante: outliers isolado, sem solo/filtro/gap — ver Seção
      3.1/3.2) estratificado por ano_lidar (campanha de aquisição), usando as
      previsões OOF já salvas.
  (b) Modelo de controle: mesmas features do ABA MENOS as duas que capturam densidade
      de varredura diretamente (pt_density, ptdens_cv) — se o R² cair pouco, a maior
      parte do sinal não vem de "reconhecer a campanha" pela densidade de pontos.

P8 — Teste pareado (Wilcoxon signed-rank) sobre o erro quadrático por parcela, OOF,
  entre CNN 2D (raster), Random Forest e CNN 3D (voxel), CADA UM na sua PRÓPRIA melhor
  variante (outliers isolado para CNN 2D/RF; sem-outliers combinado para CNN 3D, que
  não melhora com o tratamento isolado — ver Seção 3.1/3.2) — testa se a diferença de
  desempenho entre essas três arquiteturas, nas suas melhores configurações, é
  estatisticamente significativa ou só ruído de amostra.

Rodar com: EXCLUDE_OUTLIERS=1 python src/confounder_analysis.py
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, root_mean_squared_error

os.environ.setdefault("EXCLUDE_OUTLIERS", "1")
os.environ.setdefault("PREPROC", "raw")  # melhor variante do ABA é outliers ISOLADO

from train_aba import build_dataset, GBR_PARAMS, SEED, N_SPLITS, Y_FWD, Y_INV  # noqa: E402
from train_model import OUT_DIR  # noqa: E402

DENSITY_FEATURES = {"pt_density", "ptdens_cv"}


def _stratified_r2_by_campaign():
    oof = json.loads((OUT_DIR / "oof_aba_noout_raw.json").read_text())
    summ = pd.read_csv("data/processed/05_biomass/summary.csv")
    summ["plot_id"] = summ["plot_id"].astype(str)
    year_map = {(r.site, r.plot_id): r.ano_lidar for r in summ.itertuples()}

    df = pd.DataFrame({"y_true": oof["y_true"], "y_pred": oof["y_pred"],
                       "site": oof["site"], "plot": oof["plot"]})
    df["ano_lidar"] = [year_map.get((s, p)) for s, p in zip(df["site"], df["plot"])]
    df = df.dropna(subset=["ano_lidar"])
    df["ano_lidar"] = df["ano_lidar"].astype(int)

    print("R² do ABA (sem outliers) estratificado por campanha (ano_lidar):")
    rows = []
    for year, g in df.groupby("ano_lidar"):
        if len(g) < 5:
            r2 = float("nan")
        else:
            r2 = r2_score(g.y_true, g.y_pred)
        rows.append({"ano_lidar": int(year), "n": len(g), "r2": round(float(r2), 4)
                     if not np.isnan(r2) else None})
        print(f"  {year}  n={len(g):>3}  R²={r2:.3f}" if not np.isnan(r2)
             else f"  {year}  n={len(g):>3}  R²=— (n<5)")
    return rows


def _density_control_model():
    X, y, groups, labels, feat_names = build_dataset()
    drop_idx = [i for i, n in enumerate(feat_names) if n in DENSITY_FEATURES]
    keep_idx = [i for i in range(len(feat_names)) if i not in drop_idx]
    X_ctrl = X[:, keep_idx]
    dropped = [feat_names[i] for i in drop_idx]
    print(f"\nModelo de controle: {len(keep_idx)}/{len(feat_names)} features "
         f"(removidas: {dropped})")

    def _cv_r2(X_):
        kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
        all_te, all_pred = [], []
        for tr, te in kf.split(X_):
            m = GradientBoostingRegressor(**GBR_PARAMS)
            m.fit(X_[tr], Y_FWD(y[tr]))
            pred = Y_INV(m.predict(X_[te]))
            all_te.extend(y[te]); all_pred.extend(pred)
        return (r2_score(all_te, all_pred),
                root_mean_squared_error(all_te, all_pred))

    r2_full, rmse_full = _cv_r2(X)
    r2_ctrl, rmse_ctrl = _cv_r2(X_ctrl)
    print(f"  Completo (37 features):            R²={r2_full:.4f}  RMSE={rmse_full:.1f}")
    print(f"  Controle (sem densidade, {len(keep_idx)} features): "
         f"R²={r2_ctrl:.4f}  RMSE={rmse_ctrl:.1f}")
    print(f"  Diferença: ΔR²={r2_full - r2_ctrl:+.4f}")
    return {"r2_full": round(r2_full, 4), "r2_control": round(r2_ctrl, 4),
           "rmse_full": round(rmse_full, 2), "rmse_control": round(rmse_ctrl, 2),
           "dropped_features": dropped, "n_features_control": len(keep_idx)}


def _paired_test():
    models = {"CNN 2D (raster)": "oof_raster_noout_raw.json",
             "Random Forest": "oof_rf_noout_raw.json",
             "CNN 3D (voxel)": "oof_voxel_noout.json"}
    errs = {}
    for name, fname in models.items():
        d = json.loads((OUT_DIR / fname).read_text())
        df = pd.DataFrame({"y_true": d["y_true"], "y_pred": d["y_pred"],
                           "key": [f"{s}|{p}" for s, p in zip(d["site"], d["plot"])]})
        df["sq_err"] = (df.y_pred - df.y_true) ** 2
        errs[name] = df.set_index("key")["sq_err"]

    common = set.intersection(*[set(e.index) for e in errs.values()])
    print(f"\nTeste pareado (Wilcoxon signed-rank) sobre erro quadrático OOF, "
         f"{len(common)} parcelas em comum:")
    names = list(models.keys())
    results = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            ea = errs[a].loc[list(common)]
            eb = errs[b].loc[list(common)]
            stat, p = wilcoxon(ea, eb)
            sig = "significativo (p<0,05)" if p < 0.05 else "não significativo"
            print(f"  {a} vs {b}: p={p:.4f} — {sig}")
            results.append({"a": a, "b": b, "p_value": round(float(p), 4),
                           "significant_0.05": bool(p < 0.05)})
    return results


if __name__ == "__main__":
    campaign = _stratified_r2_by_campaign()
    control = _density_control_model()
    pairwise = _paired_test()
    out = {"campaign_stratified_r2": campaign, "density_control": control,
          "pairwise_wilcoxon": pairwise}
    Path(OUT_DIR / "confounder_analysis.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\nSalvo em {OUT_DIR / 'confounder_analysis.json'}")
