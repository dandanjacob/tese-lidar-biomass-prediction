> **Input:** raw point cloud — each point as (x, y, height), with no pre-computed metrics.

This model takes the **raw point cloud** — no metric extraction, no canopy filter, no
sorting. The only transformation is the one the scope accepts:

1. **Height above ground** — ground is estimated locally (minimum Z over a 1 m grid) and subtracted; each point becomes (x, y, height).
2. **Local frame** — XY centered on the plot centroid; values are divided by a fixed scale just to keep them around 1.

The `(x, y, z)` points go straight into the network. A **PointNet** is permutation-invariant
by construction: a shared MLP processes each point, a **max-pool** aggregates the whole
set into one vector, and a regression head estimates AGB. There is no point index to
match — hence no need to sort.

> For memory/CPU reasons (not feature engineering), at most 8192 points per plot are
> stored and 2048 are sampled per step. No sorting, no filtering: it is the raw cloud.
> With few plots and no GPU, overfitting is expected.
