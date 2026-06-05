The LiDAR collection (NASA/ORNL) is organized in a hierarchy:

- **Site** — monitored region (e.g. ANA, DUC, TAP).
- **Area** — a catalogued patch within a site (e.g. A01), flown in one or more **campaigns** (different years).
- **Tile** — the point cloud of each area/campaign **does not come as a single file**: it is subdivided into several **tiles**, smaller rectangular `.laz` files that are the atomic unit of data. The full NASA inventory has **3,152 tiles**.

Cross-referencing with the field inventory follows three steps:

1. **Intersection (≥ 99.9% campaign coverage)** — we keep each inventory **plot** whose polygon has **≥ 99.9% of its area inside the contiguous coverage of one campaign** (neighboring tiles from the same flight, merged; a/b subcampaigns of the same year count as one). Result: **553 plots** with coverage, spread across **242 tiles** (summing all campaigns).
2. **Smallest temporal gap** — since the same plot usually overlaps several campaigns, for each plot we keep only the campaign with the **smallest year difference** between the LiDAR flight and the field measurement. This filter selects **124** distinct tiles.
3. **Clip** — each selected tile is **cut to the plot polygon**, producing one point cloud per plot. This is what the **Clipped plots** metric tracks (step in progress).
