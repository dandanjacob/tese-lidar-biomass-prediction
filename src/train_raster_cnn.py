"""
Treina um modelo de AGB com RASTERS DE ALTURA 2D + CNN (do zero).

Ideia (Opção B): em vez de pontos crus (PointNet) ou alturas resumidas (GBR), a
parcela vira uma "imagem" vista de cima. Cada célula de uma grade GRID×GRID guarda
estatísticas de altura dos pontos que caem nela — captando também a ESTRUTURA
HORIZONTAL (clareiras, agrupamento de copas) que os outros modelos descartam.

Representação por parcela (após normalizar a altura pro solo, igual aos outros):
  - canal 0: altura máxima do dossel na célula (CHM)
  - canal 1: altura média
  - canal 2: densidade (log do nº de pontos)
  - canal 3: desvio-padrão da altura
A grade cobre a extensão XY da própria parcela (cada parcela preenche o raster).

Rede: CNN 2D pequena (3 blocos conv+BN+ReLU, pooling) → pooling global → cabeça densa.
Aumento de dados: rotações de 90° e espelhamentos (a vista de cima é invariante a isso)
— barato e ajuda contra overfit com poucas amostras.

Avaliação: leave-one-site-out (LOSO), igual ao GBR e ao PointNet (comparação justa).
Saídas:
  data/processed/06_model/model_raster.pt
  data/processed/06_model/cv_results_raster.csv
  data/processed/06_model/model_metrics_raster.json
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

from train_model import (height_above_ground, xy_inlier_mask, CANOPY_MIN_H, LAZ_DIR,
                         SUMMARY, OUT_DIR, GROUND_RADIUS, N_SPLITS, Y_FWD, Y_INV)
from outlier_filter import filter_summary, SUFFIX, VARIANT

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

SEED         = 42
GRID         = 32      # resolução do raster (GRID×GRID células)
H_SCALE      = 40.0    # m — normaliza as alturas para ~O(1)
EPOCHS       = 80
BATCH        = 32
LR           = 1e-3
WEIGHT_DECAY = 1e-4

torch.manual_seed(SEED)
np.random.seed(SEED)


def rasterize(laz_path: Path):
    """(4, GRID, GRID) float32 — rasters de altura da parcela. None se inválida."""
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

    hag = height_above_ground(x, y, z, cls, GROUND_RADIUS)
    m = hag >= CANOPY_MIN_H            # mantém só dossel (≥ altura do peito)
    if int(m.sum()) >= 50:
        x, y, hag = x[m], y[m], hag[m]
    hag = np.clip(hag, 0, None)
    dx = (x.max() - x.min()) or 1.0
    dy = (y.max() - y.min()) or 1.0
    col = np.clip(((x - x.min()) / dx * GRID).astype(int), 0, GRID - 1)
    row = np.clip(((y - y.min()) / dy * GRID).astype(int), 0, GRID - 1)
    idx = row * GRID + col
    n = GRID * GRID

    cnt = np.zeros(n, np.float64); np.add.at(cnt, idx, 1.0)
    s   = np.zeros(n, np.float64); np.add.at(s, idx, hag)
    s2  = np.zeros(n, np.float64); np.add.at(s2, idx, hag.astype(np.float64) ** 2)
    mx  = np.zeros(n, np.float64); np.maximum.at(mx, idx, hag)

    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(cnt > 0, s / cnt, 0.0)
        var = np.where(cnt > 0, s2 / cnt - mean ** 2, 0.0)
    std = np.sqrt(np.clip(var, 0, None))

    ch = np.stack([
        mx / H_SCALE,
        mean / H_SCALE,
        np.log1p(cnt) / 8.0,
        std / 20.0,
    ]).reshape(4, GRID, GRID).astype(np.float32)
    return ch


def build_dataset():
    df = filter_summary(pd.read_csv(SUMMARY))
    df = df[df["agb_m1_Mg_ha"].notna()].copy()
    items = []
    for _, row in df.iterrows():
        site, pid = row["site"], str(row["plot_id"])
        laz = LAZ_DIR / site / f"plot_{pid}.laz"
        if not laz.exists():
            continue
        r = rasterize(laz)
        if r is None:
            continue
        items.append((r, float(row["agb_m1_Mg_ha"]), site, f"{site}|{pid}"))
    log.info(f"  {len(items)} parcelas | {len(set(i[2] for i in items))} sites")
    return items


def augment(arr, rng):
    """Rotações de 90° + espelhamentos (vista de cima é invariante)."""
    arr = np.rot90(arr, rng.integers(0, 4), axes=(1, 2))
    if rng.random() < 0.5:
        arr = np.flip(arr, axis=1)
    if rng.random() < 0.5:
        arr = np.flip(arr, axis=2)
    return np.ascontiguousarray(arr)


def make_batch(items, idxs, rng, aug):
    arr = np.stack([augment(items[i][0], rng) if aug else items[i][0] for i in idxs])
    return torch.from_numpy(arr)


class RasterCNN(nn.Module):
    def __init__(self, c=4):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(c, 16, 3, padding=1), nn.BatchNorm2d(16), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.head = nn.Sequential(
            nn.Flatten(), nn.Linear(64, 64), nn.ReLU(), nn.Dropout(0.3), nn.Linear(64, 1))

    def forward(self, x):
        return self.head(self.net(x)).squeeze(-1)


def train_fold(items, tr_idx, y_mean, y_std, rng, history=None):
    model = RasterCNN()
    opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    lossf = nn.MSELoss()
    model.train()
    for _ in range(EPOCHS):
        order = rng.permutation(tr_idx)
        ep_loss, nb = 0.0, 0
        for b in range(0, len(order), BATCH):
            idxs = order[b:b + BATCH]
            if len(idxs) < 2:           # BatchNorm precisa de batch > 1
                continue
            xb = make_batch(items, idxs, rng, aug=True)
            yb = torch.tensor([(Y_FWD(items[i][1]) - y_mean) / y_std for i in idxs], dtype=torch.float32)
            opt.zero_grad()
            loss = lossf(model(xb), yb)
            loss.backward()
            opt.step()
            ep_loss += float(loss); nb += 1
        if history is not None:
            history.append(ep_loss / max(nb, 1))  # loss média da época (alvo padronizado)
    return model


@torch.no_grad()
def predict(model, items, idxs, y_mean, y_std, rng):
    model.eval()
    preds = []
    for b in range(0, len(idxs), BATCH):
        xb = make_batch(items, idxs[b:b + BATCH], rng, aug=False)
        preds.extend((model(xb).numpy() * y_std + y_mean).tolist())
    return np.array(preds)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log.info(f"Rasterizando parcelas (grade {GRID}×{GRID}, 4 canais)...")
    items = build_dataset()
    y = np.array([it[1] for it in items], dtype=np.float32)
    groups = np.array([it[2] for it in items])
    log.info(f"  AGB M1 — média {y.mean():.1f} std {y.std():.1f} [Mg/ha]")

    log.info(f"\nValidação cruzada (k-fold aleatório, {N_SPLITS} dobras, peso 1/parcela):")
    rng = np.random.default_rng(SEED)
    kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    all_te, all_pred, records = [], [], []
    for i, (tr, te) in enumerate(kf.split(np.zeros(len(items))), 1):
        y_mean, y_std = Y_FWD(y[tr]).mean(), Y_FWD(y[tr]).std() + 1e-6
        model = train_fold(items, tr, y_mean, y_std, rng)
        pred = Y_INV(predict(model, items, te, y_mean, y_std, rng))
        rmse = root_mean_squared_error(y[te], pred)
        r2 = r2_score(y[te], pred)
        rrmse = rmse / y[te].mean() * 100
        all_te.extend(y[te]); all_pred.extend(pred)
        records.append({"fold": i, "n_test": len(te), "rmse": round(rmse, 2),
                        "r2": round(r2, 4), "rrmse_pct": round(rrmse, 2)})
        log.info(f"  fold {i}  n={len(te):>3}  RMSE={rmse:.1f}  R²={r2:.3f}")

    cv = pd.DataFrame(records)
    cv.to_csv(OUT_DIR / f"cv_results_raster{SUFFIX}.csv", index=False)
    g_rmse = root_mean_squared_error(all_te, all_pred)
    g_r2 = r2_score(all_te, all_pred)
    g_rrmse = g_rmse / np.mean(all_te) * 100
    log.info(f"\n  Global ({N_SPLITS}-fold) — RMSE={g_rmse:.1f}  R²={g_r2:.3f}  rRMSE={g_rrmse:.1f}%")

    log.info("\nTreinando modelo final (todas as parcelas)...")
    y_mean, y_std = Y_FWD(y).mean(), Y_FWD(y).std() + 1e-6
    hist = []
    final = train_fold(items, np.arange(len(items)), y_mean, y_std, rng, history=hist)
    (OUT_DIR / f"history_raster{SUFFIX}.json").write_text(json.dumps({
        "x": list(range(1, len(hist) + 1)), "y": [round(v, 5) for v in hist],
        "x_kind": "epoch", "y_kind": "loss"}, ensure_ascii=False))
    torch.save({"state_dict": final.state_dict(), "y_mean": float(y_mean),
                "y_std": float(y_std), "grid": GRID, "h_scale": H_SCALE},
               OUT_DIR / f"model_raster{SUFFIX}.pt")

    metrics = {
        "key": f"raster{SUFFIX}",
        "name": "CNN 2D — rasters de altura",
        "model": "CNN 2D (rasters de altura)",
        "library": "PyTorch",
        "variant": VARIANT,
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "target": "agb_m1_Mg_ha",
        "n_plots": len(items),
        "n_sites": int(len(set(groups))),
        "n_features": f"raster {GRID}×{GRID}×4",
        "agb_mean": round(float(y.mean()), 1),
        "agb_std": round(float(y.std()), 1),
        "cv": f"K-fold aleatório ({N_SPLITS} dobras, peso 1/parcela)",
        "cv_file": f"cv_results_raster{SUFFIX}.csv",
        "approach_key": "model_approach_raster",
        "hyperparameters": {
            "arquitetura": "Conv(4→16→32→64)+BN+pool · global-pool · Linear(64→64→1)",
            "grade": f"{GRID}×{GRID}",
            "canais": "max, média, log-densidade, desvio",
            "aumento": "rot90 + flips",
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
    (OUT_DIR / f"model_metrics_raster{SUFFIX}.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False))
    log.info(f"  Métricas em {OUT_DIR / f'model_metrics_raster{SUFFIX}.json'}")


if __name__ == "__main__":
    main()
