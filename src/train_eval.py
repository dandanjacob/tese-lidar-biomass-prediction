"""Helpers compartilhados para os gráficos da página Modelos:

- Previsões out-of-fold (OOF) → predito × observado e resíduos.
- Learning curve → erro de teste conforme o tamanho do conjunto de treino cresce.

Os scripts de treino chamam `save_oof` (com o que o k-fold já calcula, custo zero) e
`learning_curve` + `save_lc` (holdout fixo, poucas frações — barato mesmo nos torch)."""

import json

import numpy as np


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
                   fractions=(0.2, 0.4, 0.6, 0.8, 1.0), test_frac=0.25):
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
