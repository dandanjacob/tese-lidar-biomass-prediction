> **Input:** 1025 features per plot — 1024 sorted canopy heights + log(total point count).

The model predicts a plot's **above-ground biomass (AGB)** from its **clipped LiDAR
point cloud** — the field inventory is not used in the prediction, it only provides the
training target. For each plot, the cloud is turned into a fixed-length vector:

1. **Height above ground** — ground is estimated locally (minimum Z over a 1 m grid) and subtracted from each point.
2. **Canopy filter** — returns below 2 m (ground and understory) are dropped.
3. **Sampling** — 1024 canopy points are drawn (padded with zeros if fewer exist).
4. **Sorting** — the 1024 heights are sorted, giving a vector invariant to point order.
5. **Density** — `log(point count)` is appended as a feature, capturing scan density.

Result: **1025 features** per plot; the target is **AGB from formula M1** (Mg/ha).
