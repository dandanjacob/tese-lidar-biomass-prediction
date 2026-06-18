> **Input:** K+1 features — K quantiles of the canopy height distribution + log(point count). K ∈ {8, 16, 32, 64, 128, 256}.

Same idea as **GBR — ordered heights**, but reducing dimensionality. Instead of 1024
sampled, sorted heights (1025 features for 493 plots — far more features than samples,
which leads the model to *memorize* the training set), each plot becomes just **K
evenly spaced quantiles** of the canopy height distribution:

1. **Height above ground** — ground estimated locally (min Z on a 1-m grid) and subtracted.
2. **Canopy filter** — returns below 1.3 m (ground and understory) are dropped.
3. **K quantiles** — the height profile is summarized at K evenly spaced points (deterministic, no random sampling). This is the same style as the ABA metrics.
4. **Density** — `log(point count)` is appended — **K + 1 features** total.

Training the same GBR (same hyperparameters, same cross-validation) for
`K ∈ {8, 16, 32, 64, 128, 256}` yields a **CV R² vs number of heights** curve: if
performance does not drop (or even improves) with fewer features, it confirms that the
original 1024 heights were largely noise that only fed overfitting.
