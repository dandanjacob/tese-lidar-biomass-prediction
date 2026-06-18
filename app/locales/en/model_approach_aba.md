> **Input:** 37 structural canopy metrics — height percentiles, canopy cover, CHM roughness and vertical density.

The plot becomes a **vector of structural metrics** — not the cloud itself. This is
the classic approach in forest LiDAR literature (*Area-Based Approach*, ABA) and,
unlike the networks, it makes explicit **which forest properties** drive the
prediction.

After normalizing height to the ground (minimum Z over a 1 m grid), **37 metrics** are
extracted in three families:

1. **Height distribution** — max, mean, std, CV, percentiles (p05…p99), skewness,
   kurtosis and the *canopy relief ratio*.
2. **Vertical density / cover** — fraction of returns above 2 m, density deciles
   (D0…D9), vertical entropy and point density.
3. **Convolutional (spatial)** — the plot becomes a **CHM** (1 m grid) and a **3×3
   Laplacian** measures canopy roughness/texture, plus *gap fraction* and spatial
   heterogeneity of point density.

These 37 metrics feed a **Gradient Boosting** model (same hyperparameters and
leave-one-site-out as the other approaches, for a fair comparison).

> It is the **best-performing** approach here — and the only **interpretable** one: the
> importance table shows that the convolutional canopy roughness and the density
> deciles are the features that weigh the most.
