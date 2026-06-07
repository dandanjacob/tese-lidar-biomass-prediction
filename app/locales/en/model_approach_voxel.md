Here the plot becomes a **3D volume**. After normalizing height above ground, space is
split into a 16×16×16 grid (plot XY × height 0 to 40 m) and each voxel stores what is
there. A **3D CNN** convolves over the volume, seeing **vertical and horizontal**
structure at once — the "fullest" of the three convolutional approaches.

Two channels per voxel:

1. **Occupancy** — 1 if the voxel holds at least one point;
2. **Density** — log of the point count in the voxel.

This forms a `16×16×16×2` tensor, processed by a **3D CNN** (3 conv3d+BN+ReLU blocks with
pooling → global pooling → dense head). Augmentation rotates the plot by 90° **in the
horizontal plane** (around the vertical axis) and flips in X/Y — the height axis is never
rotated, since canopy top and base are not interchangeable.

> 3D convolution is the most complete representation, but also the heaviest and most
> prone to overfitting: many more parameters for only ~493 plots.
