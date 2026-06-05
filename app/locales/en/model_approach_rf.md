Uses **exactly the same 37 structural metrics** as the ABA approach (height
distribution, vertical density and convolutional CHM metrics), but swaps **Gradient
Boosting** for a **Random Forest**.

The difference is how the trees are combined:

- **Random Forest** (here) — *bagging*: hundreds of deep trees trained on different
  samples and feature subsets, with the prediction being their **average**. Reduces
  variance, is robust and needs almost no tuning.
- **Gradient Boosting** (ABA) — *boosting*: shallow trees in sequence, each correcting
  the previous one's error.

It is trained on the **same dataset** (each plot weight 1, no site distinction, random
k-fold) and with the **log1p target**, so the two are directly comparable — the
performance gap comes only from the algorithm, not the features.

> It answers: over these metrics, does *bagging* or *boosting* generalize better? The
> importance table (below) shows which metrics the Random Forest relies on most.
