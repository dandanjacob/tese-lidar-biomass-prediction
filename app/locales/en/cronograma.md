## ✅ What has been done

1. **Data collection** — airborne LiDAR point clouds (NASA / ORNL DAAC) and Amazon
   field forest inventories.
2. **Understanding the data** — exploring the structure, quality and coverage of each
   source, and setting up the processing pipeline.
3. **LiDAR × inventory intersections** — spatial join to find which field plots have
   LiDAR coverage (and the year gap between the flight and the field measurement).
4. **Field-inventory biomass** — per-plot AGB computed from the inventory (DBH, height,
   wood density), in three formula variants (M1 / M2 / M3). This is the **target** the
   models try to predict.
5. **First "blind" models** — feeding the point cloud (raw or summarized) straight into
   the model, **without standardizing** the plots: GBR, Random Forest, PointNet and
   2D/3D CNNs.

## 🎯 The plan (next steps)

The first models **performed poorly** — a sign that the input data is too heterogeneous
(plots with very different areas, shapes and densities).

1. **Standardize the point clouds** — clip them all to a **more uniform area and shape**
   (a regular footprint). The benefit is twofold:
   - it yields a **much larger dataset**, since each big plot can become several smaller
     units;
   - each unit is **more precise**, representing a smaller, more homogeneous area.
2. **Re-run the models** on these **better-categorized** plots and compare against the
   "blind" run.
3. **Study more models** on this standardized dataset.
4. **Plan B — metrics instead of the raw cloud:** if the models that take the **point
   cloud as input** keep underperforming, move to models fed by **metrics extracted from
   the clouds** (max height, percentiles, density, etc.) — the area-based approach (ABA).

---

> _Living page: updated as the project moves forward._
