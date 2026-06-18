> **Input:** 32×32 2D grid — 4 channels per cell: max height, mean height, log density and std deviation.

Here the plot becomes a **top-down "image"**. After normalizing height above ground, the
points are dropped into a 32×32 grid and each cell stores height statistics — capturing
the **horizontal structure** (gaps, crown clumping) that GBR and PointNet discard.

Four channels per cell:

1. **Maximum height** (CHM — canopy height model);
2. **Mean height**;
3. **Density** (log of the point count in the cell);
4. **Standard deviation** of height.

This forms a `32×32×4` raster (a multi-channel "image"), processed by a **small 2D CNN**
(3 conv+BN+ReLU blocks with pooling → global pooling → dense head). Since the top-down
view is invariant to rotations/flips, training uses **data augmentation** (rot90 + flips)
— cheap and helps against overfitting with few plots.

> It is the only one of the three approaches that sees the forest's **horizontal**
> arrangement, not just the height profile. More parameters than the others → also the
> most sensitive to sample size.
