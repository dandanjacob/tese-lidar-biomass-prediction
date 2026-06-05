"""Página inicial — visão geral do dataset e do pipeline."""

import streamlit as st
import streamlit.components.v1 as components

from lib import charts, data
from lib.i18n import md, t, with_acronyms

st.title(t("home.title"))
st.markdown(with_acronyms(md("home_intro")), unsafe_allow_html=True)

raw = data.load_intersections()
temp = data.load_temporal()
clip = data.load_clipped_stats()

n_plots = raw.groupby(["inventory_file", "plot_id"]).ngroups
n_sites = raw["inventory_file"].nunique()
n_tiles = raw["laz_file"].nunique()
# conta pares (site, parcela) — o nome da parcela (plot_1, ...) repete entre sites
n_clipped = clip.groupby(["site", "plot"]).ngroups if not clip.empty else 0

st.markdown(f"### {t('home.dataset_status')}")
c1, c2, c3, c4 = st.columns(4)
c1.metric(t("home.metric_plots"), n_plots, help=t("home.metric_plots_help"))
c2.metric(t("home.metric_sites"), n_sites)
c3.metric(t("home.metric_tiles"), n_tiles)
c4.metric(t("home.metric_clipped"), n_clipped, help=t("home.metric_clipped_help"))

st.markdown("---")
st.markdown(f"### {t('home.data_org_title')}")
st.markdown(with_acronyms(md("data_organization")), unsafe_allow_html=True)

st.markdown("---")
st.markdown(f"### {t('home.pipeline_title')}")
st.caption(t("home.pipeline_caption"))
components.html(charts.pipeline_flow_html(t("home.pipeline_steps")), height=560)

st.markdown("---")
st.markdown(f"### {t('home.gap_title')}")
bst = data.best_match(temp)
# inclui o gap máximo (cobertura 100%) como última coluna
thresholds = [0, 1, 2, 3, int(bst["abs_gap"].max())]
cols = st.columns(len(thresholds))
for col, thr in zip(cols, thresholds):
    n = int((bst["abs_gap"] <= thr).sum())
    col.metric(t("home.gap_metric", n=thr), f"{n}", f"{100 * n // len(bst)}%")
