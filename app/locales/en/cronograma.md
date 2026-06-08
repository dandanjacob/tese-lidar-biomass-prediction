## ✅ What has been done

1. **Data collection and understanding** — airborne LiDAR point clouds (NASA / ORNL
   DAAC) and Amazon field forest inventories; exploring structure, quality and coverage.
2. **LiDAR × inventory intersections** — spatial join of the plots with LiDAR coverage,
   including the year gap between the flight and the field measurement.
3. **Reference biomass (the target)** — per-plot AGB from the inventory (DBH, height,
   wood density), in three formulas (M1 / M2 / M3).
4. **Dataset recovery** — deduplication and fixes raised the usable plots from
   **383 → 493** (and **325** after removing area/shape outliers).
5. **Six models, two variants** — GBR, Random Forest, ABA (metrics), PointNet and 2D/3D
   CNNs, trained **with and without outliers** and evaluated by k-fold cross-validation.
6. **Per-model diagnostics** — predicted vs observed, residuals, learning curve and
   training evolution (RMSE + R²); on the point cloud, an overlay of the inventory trees
   (position, height, species) and the LiDAR × inventory time-gap metric.
7. **Dimensionality reduction (experiment)** — GBR on **K height quantiles** (from 8 to
   256): R² already saturates at **~16 quantiles** (~0.44 without outliers), confirming
   that the original 1024 heights were largely noise feeding *overfitting*.

## 🎯 The plan (next steps)

Read so far: **a few well-chosen features (ABA / quantiles) generalize better than the
high-dimensional raw cloud**, and removing outliers helps a lot.

1. **Standardize the plot footprint** — clip them all to a similar area and shape,
   yielding a larger, more homogeneous dataset (each big plot becomes several smaller
   units).
2. **Deepen the metrics / ABA approach** and regularization, since it beats the raw cloud.
3. **Fix the PyTorch models** — the voxel CNN still does worse than predicting the mean
   (R² < 0): early stopping and less capacity.
4. **Re-run and compare** everything on the standardized dataset.

---

> _Living page: updated as the project moves forward._
