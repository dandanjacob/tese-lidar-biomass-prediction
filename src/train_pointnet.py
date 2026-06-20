"""
Treina um modelo de AGB direto da NUVEM DE PONTOS CRUA (PointNet/DeepSets).

Diferença para train_model.py (modelo tabular): aqui NÃO há extração de métricas,
filtro de dossel nem ordenação. A nuvem entra praticamente crua:

  1. Altura sobre o solo: solo = mínimo de Z numa grade local (mesma de train_model);
     z vira altura acima do solo (HAG). É a única normalização — aceita pelo escopo.
  2. XY centrado no centroide da parcela (translação para o referencial local).
  3. Os pontos (x, y, z) são divididos por uma escala fixa só para ficarem ~O(1).
  Nenhum filtro (≥2 m), nenhuma ordenação, nenhuma feature feita à mão.

A rede é invariante à ordem por construção: MLP compartilhado por ponto → max-pool
simétrico → cabeça de regressão. Por isso não precisa ordenar nem casar índices de
ponto: ela aprende direto do conjunto de pontos.

Restrição prática (memória/CPU, não engenharia de feature): guarda-se no máximo
N_STORE pontos por parcela (subamostra aleatória uma vez) e treina-se com N_SAMPLE
pontos sorteados por época. Sem GPU, mantemos a rede pequena.

Avaliação: leave-one-site-out (LOSO), igual ao tabular, para comparar de forma justa.
Saídas:
  data/processed/06_model/model_pointnet.pt
  data/processed/06_model/cv_results_pointnet.csv
  data/processed/06_model/model_metrics_pointnet.json
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import laspy
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import KFold
from sklearn.metrics import root_mean_squared_error, r2_score

from train_model import (height_above_ground, xy_inlier_mask, CANOPY_FILTER_H, LAZ_DIR,
                         SUMMARY, OUT_DIR, GROUND_RADIUS, N_SPLITS, Y_FWD, Y_INV)
from outlier_filter import filter_summary, SUFFIX, VARIANT, TARGET
from train_eval import save_oof, save_lc, learning_curve

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

SEED        = 42
N_STORE     = 8192     # máx. de pontos guardados por parcela (limite de memória)
N_SAMPLE    = 2048     # pontos sorteados por parcela a cada passo (sem ordenar)
XYZ_SCALE   = 30.0     # m — divide xyz só para deixar a entrada ~O(1)
EPOCHS      = 60
BATCH       = 32
LR          = 1e-3
WEIGHT_DECAY = 1e-4

torch.manual_seed(SEED)
np.random.seed(SEED)


def load_raw_points(laz_path: Path, rng: np.random.Generator):
    """(P, 3) float32 com a nuvem crua: XY centrado, Z = altura sobre o solo, /escala.
    Sem filtro de dossel, sem ordenação. None se nuvem pequena/implausível."""
    try:
        las = laspy.read(laz_path)
        x = np.array(las.x, dtype=np.float64)
        y = np.array(las.y, dtype=np.float64)
        z = np.array(las.z, dtype=np.float32)
        cls = np.array(las.classification, dtype=np.uint8)
    except Exception as e:
        log.warning(f"  [SKIP] {laz_path.name}: {e}")
        return None
    if len(z) < 100:
        return None
    keep = xy_inlier_mask(x, y)
    x, y, z, cls = x[keep], y[keep], z[keep], cls[keep]
    if (x.max() - x.min()) > 1000 or (y.max() - y.min()) > 1000:
        log.warning(f"  [SKIP] {laz_path.name}: extent implausível")
        return None

    hag = height_above_ground(x, y, z, cls, GROUND_RADIUS)        # altura sobre o solo (DTM classe 2)
    m = hag >= CANOPY_FILTER_H         # mantém só dossel (≥ altura do peito); -inf desliga
    if int(m.sum()) >= 50:
        x, y, hag = x[m], y[m], hag[m]
    pts = np.stack([(x - x.mean()), (y - y.mean()), hag], axis=1).astype(np.float32)
    pts /= XYZ_SCALE
    if len(pts) > N_STORE:                                        # limite de memória
        pts = pts[rng.choice(len(pts), N_STORE, replace=False)]
    return pts


def build_dataset():
    """Lista de (pts, agb, site, label) com a nuvem crua de cada parcela."""
    df = filter_summary(pd.read_csv(SUMMARY))
    df = df[df[TARGET].notna()].copy()
    rng = np.random.default_rng(SEED)
    items = []
    for _, row in df.iterrows():
        site, pid = row["site"], str(row["plot_id"])
        laz = LAZ_DIR / site / f"plot_{pid}.laz"
        if not laz.exists():
            continue
        pts = load_raw_points(laz, rng)
        if pts is None:
            continue
        items.append((pts, float(row[TARGET]), site, f"{site}|{pid}"))
    log.info(f"  {len(items)} parcelas | {len(set(i[2] for i in items))} sites")
    return items


def sample_batch(items, idxs, rng):
    """Empilha N_SAMPLE pontos sorteados (com reposição se faltar) de cada parcela."""
    out = np.empty((len(idxs), N_SAMPLE, 3), dtype=np.float32)
    for k, i in enumerate(idxs):
        pts = items[i][0]
        sel = rng.integers(0, len(pts), N_SAMPLE) if len(pts) < N_SAMPLE \
            else rng.choice(len(pts), N_SAMPLE, replace=False)
        out[k] = pts[sel]
    return torch.from_numpy(out)


class PointNetReg(nn.Module):
    """PointNet mínimo: MLP por ponto → max-pool → cabeça de regressão."""
    def __init__(self):
        super().__init__()
        self.enc = nn.Sequential(
            nn.Linear(3, 64), nn.ReLU(),
            nn.Linear(64, 128), nn.ReLU(),
        )
        self.head = nn.Sequential(
            nn.Linear(128, 64), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(64, 1),
        )

    def forward(self, x):                 # x: (B, N, 3)
        p = self.enc(x)                   # (B, N, 128)
        g = p.max(dim=1).values           # (B, 128) — pooling simétrico (invariante à ordem)
        return self.head(g).squeeze(-1)   # (B,)


def train_fold(items, tr_idx, y_mean, y_std, rng, history=None):
    model = PointNetReg()
    opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    lossf = nn.MSELoss()
    model.train()
    yt_hist = np.array([items[i][1] for i in tr_idx], dtype=float) if history is not None else None
    for _ in range(EPOCHS):
        order = rng.permutation(tr_idx)
        for b in range(0, len(order), BATCH):
            idxs = order[b:b + BATCH]
            xb = sample_batch(items, idxs, rng)
            yb = torch.tensor([(Y_FWD(items[i][1]) - y_mean) / y_std for i in idxs], dtype=torch.float32)
            opt.zero_grad()
            loss = lossf(model(xb), yb)
            loss.backward()
            opt.step()
        if history is not None:  # RMSE/R² no treino ao fim de cada época
            p = Y_INV(predict(model, items, tr_idx, y_mean, y_std, rng))
            history.append((float(root_mean_squared_error(yt_hist, p)), float(r2_score(yt_hist, p))))
            model.train()
    return model


@torch.no_grad()
def predict(model, items, idxs, y_mean, y_std, rng):
    model.eval()
    preds = []
    for b in range(0, len(idxs), BATCH):
        xb = sample_batch(items, idxs[b:b + BATCH], rng)
        preds.extend((model(xb).numpy() * y_std + y_mean).tolist())
    return np.array(preds)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log.info(f"Carregando nuvens CRUAS (store={N_STORE}, sample={N_SAMPLE} pts)...")
    items = build_dataset()
    y = np.array([it[1] for it in items], dtype=np.float32)
    groups = np.array([it[2] for it in items])
    labels = np.array([it[3] for it in items])
    log.info(f"  AGB M1 — média {y.mean():.1f} std {y.std():.1f} [Mg/ha]")

    log.info(f"\nValidação cruzada (k-fold aleatório, {N_SPLITS} dobras, peso 1/parcela):")
    rng = np.random.default_rng(SEED)
    kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    all_te, all_pred, all_lab, records = [], [], [], []
    for i, (tr, te) in enumerate(kf.split(np.zeros(len(items))), 1):
        y_mean, y_std = Y_FWD(y[tr]).mean(), Y_FWD(y[tr]).std() + 1e-6
        model = train_fold(items, tr, y_mean, y_std, rng)
        pred = Y_INV(predict(model, items, te, y_mean, y_std, rng))
        rmse = root_mean_squared_error(y[te], pred)
        r2 = r2_score(y[te], pred)
        rrmse = rmse / y[te].mean() * 100
        all_te.extend(y[te]); all_pred.extend(pred); all_lab.extend(labels[te])
        records.append({"fold": i, "n_test": len(te), "rmse": round(rmse, 2),
                        "r2": round(r2, 4), "rrmse_pct": round(rrmse, 2)})
        log.info(f"  fold {i}  n={len(te):>3}  RMSE={rmse:.1f}  R²={r2:.3f}")

    cv = pd.DataFrame(records)
    cv.to_csv(OUT_DIR / f"cv_results_pointnet{SUFFIX}.csv", index=False)
    save_oof(OUT_DIR / f"oof_pointnet{SUFFIX}.json", all_te, all_pred, all_lab)

    def _lc_eval(tr, te):
        ym, ys = Y_FWD(y[tr]).mean(), Y_FWD(y[tr]).std() + 1e-6
        m = train_fold(items, tr, ym, ys, rng)
        return root_mean_squared_error(y[te], Y_INV(predict(m, items, te, ym, ys, rng)))
    sizes, rmses = learning_curve(len(items), SEED, _lc_eval)
    save_lc(OUT_DIR / f"lc_pointnet{SUFFIX}.json", sizes, rmses)
    g_rmse = root_mean_squared_error(all_te, all_pred)
    g_r2 = r2_score(all_te, all_pred)
    g_rrmse = g_rmse / np.mean(all_te) * 100
    log.info(f"\n  Global ({N_SPLITS}-fold) — RMSE={g_rmse:.1f}  R²={g_r2:.3f}  rRMSE={g_rrmse:.1f}%")

    log.info("\nTreinando modelo final (todas as parcelas)...")
    y_mean, y_std = Y_FWD(y).mean(), Y_FWD(y).std() + 1e-6
    hist = []
    final = train_fold(items, np.arange(len(items)), y_mean, y_std, rng, history=hist)
    torch.save({"state_dict": final.state_dict(), "y_mean": float(y_mean),
                "y_std": float(y_std), "n_sample": N_SAMPLE, "xyz_scale": XYZ_SCALE},
               OUT_DIR / f"model_pointnet{SUFFIX}.pt")
    (OUT_DIR / f"history_pointnet{SUFFIX}.json").write_text(json.dumps({
        "x": list(range(1, len(hist) + 1)),
        "rmse": [round(h[0], 3) for h in hist], "r2": [round(h[1], 4) for h in hist],
        "x_kind": "epoch"}, ensure_ascii=False))

    metrics = {
        "key": f"pointnet{SUFFIX}",
        "name": "PointNet — nuvem crua",
        "model": "PointNet (MLP por ponto + max-pool)",
        "library": "PyTorch",
        "variant": VARIANT,
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "target": TARGET,
        "n_plots": len(items),
        "n_sites": int(len(set(groups))),
        "n_features": "XYZ (cru)",
        "agb_mean": round(float(y.mean()), 1),
        "agb_std": round(float(y.std()), 1),
        "cv": f"K-fold aleatório ({N_SPLITS} dobras, peso 1/parcela)",
        "cv_file": f"cv_results_pointnet{SUFFIX}.csv",
        "approach_key": "model_approach_pointnet",
        "hyperparameters": {
            "arquitetura": "Linear(3→64→128) · max-pool · Linear(128→64→1)",
            "n_sample_pts": N_SAMPLE,
            "n_store_pts": N_STORE,
            "epochs": EPOCHS,
            "batch_size": BATCH,
            "learning_rate": LR,
            "weight_decay": WEIGHT_DECAY,
            "dropout": 0.3,
        },
        "cv_global": {"rmse": round(float(g_rmse), 2), "r2": round(float(g_r2), 4),
                      "rrmse_pct": round(float(g_rrmse), 2)},
        "cv_fold_mean": {"rmse": round(float(cv.rmse.mean()), 2),
                         "r2": round(float(cv.r2.mean()), 4),
                         "rrmse_pct": round(float(cv.rrmse_pct.mean()), 2)},
    }
    (OUT_DIR / f"model_metrics_pointnet{SUFFIX}.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False))
    log.info(f"  Métricas em {OUT_DIR / f'model_metrics_pointnet{SUFFIX}.json'}")


if __name__ == "__main__":
    main()
