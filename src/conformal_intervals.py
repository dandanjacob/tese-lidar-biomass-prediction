"""Intervalo de predição por conformal prediction (split conformal) sobre os
resíduos OOF já salvos — P6 da auditoria científica.

Split conformal simples: separa os resíduos OOF de cada modelo em calibração (50%) e
avaliação (50%), com seed fixa. O raio do intervalo é o quantil empírico (1-alpha) dos
resíduos absolutos NA CALIBRAÇÃO; a cobertura reportada é medida na metade de AVALIAÇÃO
(held-out da calibração) — evita o otimismo de calibrar e medir cobertura no mesmo dado.

Não re-treina nenhum modelo: usa só os pares (y_true, y_pred) já salvos em
`oof_*.json` pelos scripts de treino. Alpha = 0.10 → intervalo de 90% de confiança.

Rodar com: python src/conformal_intervals.py
"""
import json
from pathlib import Path

import numpy as np

OUT_DIR = Path("data/processed/06_model")
ALPHA = 0.10
SEED = 42

MODELS = {
    "CNN 2D (raster)": "oof_raster_noout.json",
    "Random Forest": "oof_rf_noout.json",
    "ABA": "oof_aba_noout.json",
    "GBR 32 quantis": "oof_gbrh32_noout.json",
    "CNN 3D (voxel)": "oof_voxel_noout.json",
    "PointNet": "oof_pointnet_gap_noout.json",
}


def split_conformal(y_true, y_pred, alpha, seed):
    resid = np.abs(np.asarray(y_pred) - np.asarray(y_true))
    n = len(resid)
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    half = n // 2
    calib_idx, eval_idx = idx[:half], idx[half:]

    calib_resid = resid[calib_idx]
    # Correção finite-sample do split conformal: quantil (1-alpha) de ordem
    # ceil((n_calib+1)(1-alpha))/n_calib, não o quantil ingênuo.
    q_level = min(1.0, np.ceil((len(calib_resid) + 1) * (1 - alpha)) / len(calib_resid))
    radius = float(np.quantile(calib_resid, q_level))

    eval_resid = resid[eval_idx]
    coverage = float(np.mean(eval_resid <= radius))
    return radius, coverage, len(calib_idx), len(eval_idx)


def main():
    results = []
    print(f"Conformal prediction (split, alpha={ALPHA}, intervalo {100*(1-ALPHA):.0f}%):\n")
    for name, fname in MODELS.items():
        path = OUT_DIR / fname
        if not path.exists():
            print(f"  [SKIP] {name}: {fname} não encontrado")
            continue
        d = json.loads(path.read_text())
        radius, coverage, n_calib, n_eval = split_conformal(
            d["y_true"], d["y_pred"], ALPHA, SEED)
        print(f"  {name:<20} ±{radius:>6.1f} Mg/ha  |  cobertura empírica no held-out: "
             f"{coverage*100:.1f}% (nominal {100*(1-ALPHA):.0f}%)  "
             f"[calib n={n_calib}, eval n={n_eval}]")
        results.append({"model": name, "radius_mg_ha": round(radius, 1),
                        "empirical_coverage": round(coverage, 4),
                        "nominal_coverage": round(1 - ALPHA, 2),
                        "n_calib": n_calib, "n_eval": n_eval})

    out_path = OUT_DIR / "conformal_intervals.json"
    out_path.write_text(json.dumps(
        {"alpha": ALPHA, "seed": SEED, "results": results},
        indent=2, ensure_ascii=False))
    print(f"\nSalvo em {out_path}")


if __name__ == "__main__":
    main()
