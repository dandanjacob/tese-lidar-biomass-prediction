"""Helpers compartilhados para os gráficos da página Modelos:

- Previsões out-of-fold (OOF) → predito × observado e resíduos.
- Learning curve → erro de teste conforme o tamanho do conjunto de treino cresce.
- Métricas extras (bias, MAE, slope) → complementam RMSE/R²/rRMSE.

Os scripts de treino chamam `save_oof` (com o que o k-fold já calcula, custo zero),
`learning_curve` + `save_lc` (holdout fixo, poucas frações — barato mesmo nos torch) e
`extra_metrics` (bias/MAE/slope sobre qualquer par y_true/y_pred). Validação sempre
mescla os sites (embaralha todas as parcelas, k-fold aleatório) — sites vão de 2 a 176
parcelas, desbalanceado demais pra um split por site dar folds comparáveis entre si."""

import json

import numpy as np
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score


def save_oof(path, y_true, y_pred, labels):
    """Salva as previsões out-of-fold (uma por parcela): y real, y previsto, site e
    plot_id. `labels` são as strings "site|plot_id" (alinhadas a y_true/y_pred)."""
    sites, plots = [], []
    for lab in labels:
        s, _, p = str(lab).partition("|")
        sites.append(s)
        plots.append(p)
    path.write_text(json.dumps({
        "y_true": [round(float(v), 3) for v in y_true],
        "y_pred": [round(float(v), 3) for v in y_pred],
        "site": sites,
        "plot": plots,
    }, ensure_ascii=False))


def learning_curve(n, seed, eval_size,
                   fractions=tuple(round(i * 0.05, 2) for i in range(1, 21)),
                   test_frac=0.25):
    """Holdout fixo (test_frac do total). Para cada fração do pool de treino, chama
    `eval_size(tr_idx, te_idx) -> RMSE` e devolve (sizes, rmses). Um treino por fração
    (barato): mostra se mais dados ajudariam."""
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    n_test = max(1, int(round(n * test_frac)))
    te = perm[:n_test]
    pool = perm[n_test:]
    sizes, rmses = [], []
    for f in fractions:
        k = max(2, int(round(len(pool) * f)))
        rmses.append(round(float(eval_size(pool[:k], te)), 3))
        sizes.append(int(k))
    return sizes, rmses


def save_lc(path, sizes, rmses):
    path.write_text(json.dumps(
        {"sizes": sizes, "rmse": rmses, "x_kind": "train_size", "y_kind": "rmse"},
        ensure_ascii=False))


def extra_metrics(y_true, y_pred) -> dict:
    """Bias (erro médio, previsto−observado — viés sistemático de super/sub-estimação),
    MAE (mais robusto a outlier que RMSE) e slope/intercept da reta OLS previsto~observado
    (diagnostica saturação: slope<1 = subestima parcelas de alta biomassa e superestima
    as de baixa — padrão clássico em AGB por LiDAR, mais informativo que o bias sozinho,
    que pode ficar perto de zero mesmo com esse viés em X)."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    bias = float(np.mean(y_pred - y_true))
    mae = float(mean_absolute_error(y_true, y_pred))
    slope, intercept = np.polyfit(y_true, y_pred, 1)
    return {"bias": round(bias, 2), "mae": round(mae, 2),
           "slope": round(float(slope), 4), "intercept": round(float(intercept), 2)}
