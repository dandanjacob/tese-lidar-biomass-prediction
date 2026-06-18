## ✅ What has been done

1. **Data collection and understanding** — airborne LiDAR point clouds (NASA / ORNL
   DAAC) and Amazon field forest inventories; exploring structure, quality and coverage.
2. **LiDAR × inventory intersections** — spatial join of the plots with LiDAR coverage,
   including the year gap between the flight and the field measurement.
3. **Reference biomass (the target)** — per-plot AGB from the inventory (DBH, height,
   wood density), in three formulas (M1 / M2 / M3).
4. **Dataset recovery** — deduplication and fixes raised the usable plots from
   **383 → 493** (and **325** after removing area/shape outliers). **Transect** sites
   (TAP) whose plots were lines — not polygons — were recovered via corridor buffering:
   **24 → 27 sites** processed.
5. **Improved tree height** — 3-tier estimate (measured → site-local H-D fit → regional
   Feldpausch), recovering the per-tree measurement date from the inventory.
6. **Temporal-gap correction** — DBH is "grown" to the LiDAR flight year by the annual
   increment (observed from re-measurement → site median → default) and height and
   biomass are re-derived. Measured effect: ~1.3% on mean biomass (up to ~7–12% in sites
   with a 2–3 year gap). Adds new columns, without overwriting the originals.
7. **Six models, three variants** — GBR, Random Forest, ABA (metrics), PointNet and 2D/3D
   CNNs, trained **with outliers**, **without outliers** and **with gap + without
   outliers**, by k-fold cross-validation. Current best: the **2D height-raster CNN** at
   **R² ≈ 0.53 / rRMSE ≈ 44.5%** (gap + no outliers) — in the range of NASA's GEDI
   mission at the *footprint* level (R² ~0.4–0.5, tropical rRMSE ~47%).
8. **Diagnostics and visualization** — predicted vs observed, residuals, learning curve
   and training evolution (RMSE + R²); comparison table with a **green→red gradient** per
   metric; on the point cloud, a selector between current vs gap-corrected height and an
   option to hide the cloud to see only the heights.
9. **Dimensionality reduction (experiment)** — GBR on **K height quantiles** (from 8 to
   256): R² already saturates at **~16 quantiles**, confirming the original 1024 heights
   were largely noise feeding *overfitting*.

## 🎯 The plan (next steps)

Read so far: **a few well-chosen features generalize better than the high-dimensional
raw cloud**; removing outliers and correcting the gap help; and horizontal structure
(rasters) carries real signal. No new data can be added — the focus is squeezing more
signal and evaluating honestly.

1. **Ensemble / stacking the models** — a simple average of raster + RF + voxel already
   measures **R² ≈ 0.59** (above the best single model, 0.53). The most immediate gain.
2. **Honest evaluation (LOSO)** — the current CV is random k-fold (plots from the same
   site in both train and test), which **inflates R²** through spatial correlation.
   Report leave-one-site-out as the generalization-to-new-sites number too.
3. **Improve the weak models** — geometric augmentation for PointNet (rotation about the
   vertical axis + jitter; currently the worst, R² ~0.17) and a **hybrid raster + ABA
   metrics** model.
4. **Label quality** — tiny plots (~0.02 ha) yield implausible AGB (up to 1552 Mg/ha) and
   distort the metrics; evaluate a minimum-area floor and a robust loss.
5. **Standardize the plot footprint** — clip them all to a similar area and shape,
   yielding a more homogeneous dataset (each big plot becomes several smaller units).

---

> _Living page: updated as the project moves forward._
