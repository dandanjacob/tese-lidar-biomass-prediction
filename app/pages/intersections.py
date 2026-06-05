"""Análise de interseções LiDAR × inventário e gap temporal."""

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import data
from lib.i18n import t
from lib.theme import C_BLUE, C_LIGHT, C_PINK

st.title(t("intersections.title"))
st.markdown(t("intersections.intro"))

temp = data.load_temporal()
bst = data.best_match(temp)

color_map = {
    t("intersections.cat_same_year"): C_BLUE,
    t("intersections.cat_le2"): C_LIGHT,
    t("intersections.cat_gt2"): C_PINK,
}


def gap_category(g):
    if g == 0:
        return t("intersections.cat_same_year")
    return t("intersections.cat_le2") if abs(g) <= 2 else t("intersections.cat_gt2")


gap_all = (
    temp.drop_duplicates(["nome_area_inventario", "plot_id", "campanha_lidar"])
    .groupby("gap_temporal_anos").size().reset_index(name="n_pares")
    .sort_values("gap_temporal_anos")
)
gap_all["categoria"] = gap_all["gap_temporal_anos"].apply(gap_category)

gap_best = (
    bst.groupby("gap_temporal_anos").size().reset_index(name="n_parcelas")
    .sort_values("gap_temporal_anos")
)
gap_best["categoria"] = gap_best["gap_temporal_anos"].apply(gap_category)

total_all = int(gap_all["n_pares"].sum())
total_best = int(gap_best["n_parcelas"].sum())

# Mesma escala e mesmo tamanho nos dois gráficos (comparação direta).
y_max = max(gap_all["n_pares"].max(), gap_best["n_parcelas"].max()) * 1.18
g_lo = min(gap_all["gap_temporal_anos"].min(), gap_best["gap_temporal_anos"].min()) - 0.6
g_hi = max(gap_all["gap_temporal_anos"].max(), gap_best["gap_temporal_anos"].max()) + 0.6
CHART_H = 380


def gap_bar(df, ycol, ylabel):
    # Sem legenda nos dois (as cores estão na nota) → área de plot idêntica e mesma altura.
    fig = px.bar(df, x="gap_temporal_anos", y=ycol, color="categoria",
                 color_discrete_map=color_map, text=ycol,
                 labels={"gap_temporal_anos": t("intersections.label_gap"),
                         ycol: ylabel, "categoria": ""})
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=False, height=CHART_H, margin=dict(t=10, b=10))
    fig.update_yaxes(range=[0, y_max])
    fig.update_xaxes(range=[g_lo, g_hi], dtick=1)
    return fig


col1, col2 = st.columns(2)
with col1:
    st.subheader(t("intersections.all_subheader"))
    st.caption(t("intersections.all_caption"))
    st.plotly_chart(gap_bar(gap_all, "n_pares", t("intersections.label_pairs")),
                    use_container_width=True)
    st.markdown(t("intersections.all_desc", n=total_all))

with col2:
    st.subheader(t("intersections.best_subheader"))
    st.caption(t("intersections.best_caption"))
    st.plotly_chart(gap_bar(gap_best, "n_parcelas", t("intersections.label_plots")),
                    use_container_width=True)
    st.markdown(t("intersections.best_desc", n=total_best))

st.caption(t("intersections.chart_note"))

# ── Cobertura do inventário pelo LiDAR ──
st.markdown("---")
st.markdown(f"### {t('intersections.coverage_title')}")
st.markdown(t("intersections.coverage_intro"))

cov = data.coverage_stats()
na = t("intersections.cov_unavailable")


def cov_val(key):
    v = cov.get(key)
    return na if v is None else f"{v}"


r1 = st.columns(4)
r1[0].metric(t("intersections.cov_total"), cov["total"])
r1[1].metric(t("intersections.cov_kept"), cov["kept"], help=t("intersections.cov_kept_help"))
r1[2].metric(t("intersections.cov_discarded"), cov["discarded"],
             help=t("intersections.cov_discarded_help"))
r1[3].metric(t("intersections.cov_no_overlap"), cov["no_overlap"],
             help=t("intersections.cov_no_overlap_help"))

r2 = st.columns(4)
r2[0].metric(t("intersections.cov_corrupt_pc"), cov_val("corrupt_pointclouds"),
             help=t("intersections.cov_corrupt_pc_help"))
r2[1].metric(t("intersections.cov_corrupt_inv"), cov["corrupt_inventory"],
             help=t("intersections.cov_corrupt_inv_help"))

st.markdown("---")
st.markdown(f"### {t('intersections.threshold_title')}")
rows = [{t("intersections.col_threshold"): t("intersections.threshold_row", n=thr),
         t("intersections.col_plots"): int((bst["abs_gap"] <= thr).sum()),
         "%": f"{100 * (bst['abs_gap'] <= thr).sum() // len(bst)}%"}
        for thr in [0, 1, 2, 3]]
st.table(pd.DataFrame(rows))
