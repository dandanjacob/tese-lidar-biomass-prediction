"""Análise de biomassa (AGB) por fórmula alométrica."""

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import data
from lib.i18n import md, t, with_acronyms
from lib.theme import C_BLUE, C_LIGHT, C_RED

st.title(t("biomass.title"))
st.caption(with_acronyms(t("biomass.caption")), unsafe_allow_html=True)
st.markdown(t("biomass.intro"))

with st.expander(t("formulas.expander")):
    st.markdown(with_acronyms(md("formulas_body")), unsafe_allow_html=True)

bio = data.load_biomass_summary()
if bio.empty:
    st.warning(t("biomass.no_data"))
    st.stop()

# coluna do CSV → rótulo traduzido
FORMULA_NAMES = {
    "agb_m1_Mg_ha": t("formulas.m1_short"),
    "agb_m2_Mg_ha": t("formulas.m2_short"),
    "agb_m3_Mg_ha": t("formulas.m3_short"),
}
FORMULA_COLORS = {
    t("formulas.m1_short"): C_BLUE,
    t("formulas.m2_short"): C_LIGHT,
    t("formulas.m3_short"): C_RED,
}
# escala comum a todos os gráficos de AGB
AGB_MAX = float(bio[list(FORMULA_NAMES)].max().max())

# ── métricas gerais ──
c1, c2, c3, c4 = st.columns(4)
c1.metric(t("biomass.metric_plots"), len(bio))
c2.metric(t("biomass.metric_sites"), bio["site"].nunique())
c3.metric(t("biomass.metric_median_m1"), f"{bio['agb_m1_Mg_ha'].median():.1f} Mg/ha")
c4.metric(t("biomass.metric_median_m3"), f"{bio['agb_m3_Mg_ha'].median():.1f} Mg/ha")

st.markdown("---")

tab1, tab2, tab3 = st.tabs([t("biomass.tab_region"), t("biomass.tab_variability"),
                            t("biomass.tab_comparison")])

# ── tab 1: AGB por parcela (uma barra por plot), agrupada pelas 3 fórmulas ──
with tab1:
    st.markdown(f"**{t('biomass.region_header')}**")
    bio_lbl = bio.copy()
    bio_lbl["plot_label"] = bio_lbl["site_short"] + " / " + bio_lbl["plot_id"].astype(str)
    # ordena as parcelas pela AGB da M1 (gráfico lido de baixo p/ cima)
    order = bio_lbl.sort_values("agb_m1_Mg_ha")["plot_label"].tolist()
    long_rows = []
    for col, label in FORMULA_NAMES.items():
        sub = bio_lbl[["plot_label", col]].rename(columns={col: "agb"})
        sub["formula"] = label
        long_rows.append(sub)
    df_long = pd.concat(long_rows, ignore_index=True)

    fig = px.bar(
        df_long, x="agb", y="plot_label", color="formula", barmode="group",
        orientation="h", color_discrete_map=FORMULA_COLORS,
        category_orders={"plot_label": order},
        labels={"agb": t("biomass.region_xlabel"), "plot_label": "",
                "formula": t("biomass.label_formula")},
        title=t("biomass.region_chart_title"),
    )
    fig.update_xaxes(range=[0, AGB_MAX * 1.05])
    fig.update_layout(height=max(400, len(bio_lbl) * 22 + 140),
                      margin=dict(l=0, r=20, t=40, b=20),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0,
                                  xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(t("biomass.region_desc"))

# ── tab 2: variabilidade por site (mesma escala/tamanho entre fórmulas) ──
with tab2:
    formula_sel = st.selectbox(t("biomass.variability_formula"),
                               list(FORMULA_NAMES.values()), key="var_formula")
    col_sel = {v: k for k, v in FORMULA_NAMES.items()}[formula_sel]

    fig_box = px.box(
        bio.sort_values("site_short"), x="site_short", y=col_sel, color="site_short",
        labels={col_sel: t("biomass.variability_ylabel"), "site_short": ""},
        title=t("biomass.variability_title", formula=formula_sel), points="all",
    )
    fig_box.update_yaxes(range=[0, AGB_MAX * 1.05])
    fig_box.update_layout(height=480, showlegend=False, margin=dict(t=50, b=80),
                          xaxis_tickangle=-35)
    st.plotly_chart(fig_box, use_container_width=True)
    st.markdown(t("biomass.variability_desc"))

    st.markdown(f"**{t('biomass.variability_stats')}**")
    stats = (
        bio.groupby("site_short")[col_sel]
        .agg(**{t("biomass.stats_n"): "count", t("biomass.stats_mean"): "mean",
                t("biomass.stats_median"): "median", t("biomass.stats_std"): "std",
                t("biomass.stats_min"): "min", t("biomass.stats_max"): "max"})
        .round(1).reset_index().rename(columns={"site_short": t("biomass.col_site")})
    )
    st.dataframe(stats, hide_index=True, use_container_width=True)

# ── tab 3: comparação entre fórmulas (3 pares, mesma escala) ──
with tab3:
    st.markdown(t("biomass.comparison_desc"))
    lim = AGB_MAX * 1.05

    def scatter_pair(xcol, ycol, xlab, ylab, title):
        fig = px.scatter(
            bio, x=xcol, y=ycol, color="site_short", hover_data=["plot_id"],
            labels={xcol: xlab, ycol: ylab, "site_short": t("biomass.col_site")},
            title=title,
        )
        fig.add_shape(type="line", x0=0, y0=0, x1=lim, y1=lim,
                      line=dict(dash="dash", color="gray", width=1))
        fig.update_xaxes(range=[0, lim])
        fig.update_yaxes(range=[0, lim])
        fig.update_layout(height=380, showlegend=False, margin=dict(t=40))
        return fig

    pairs = [
        (t("biomass.comparison_m1m2"),
         scatter_pair("agb_m1_Mg_ha", "agb_m2_Mg_ha", t("biomass.comparison_m1m2_x"),
                      t("biomass.comparison_m1m2_y"), t("biomass.comparison_m1m2_title"))),
        (t("biomass.comparison_m1m3"),
         scatter_pair("agb_m1_Mg_ha", "agb_m3_Mg_ha", t("biomass.comparison_m1m3_x"),
                      t("biomass.comparison_m1m3_y"), t("biomass.comparison_m1m3_title"))),
        (t("biomass.comparison_m2m3"),
         scatter_pair("agb_m2_Mg_ha", "agb_m3_Mg_ha", t("biomass.comparison_m2m3_x"),
                      t("biomass.comparison_m2m3_y"), t("biomass.comparison_m2m3_title"))),
    ]
    cols = st.columns(3)
    for col, (header, fig) in zip(cols, pairs):
        with col:
            st.markdown(header)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"**{t('biomass.diff_header')}**")
    bio["diff_m1_m2"] = (bio["agb_m1_Mg_ha"] - bio["agb_m2_Mg_ha"]).abs()
    bio["diff_m1_m3"] = (bio["agb_m1_Mg_ha"] - bio["agb_m3_Mg_ha"]).abs()
    diff_stats = (
        bio.groupby("site_short")[["diff_m1_m2", "diff_m1_m3"]]
        .mean().round(1).reset_index()
        .rename(columns={"site_short": t("biomass.col_site"),
                         "diff_m1_m2": t("biomass.col_diff_m1m2"),
                         "diff_m1_m3": t("biomass.col_diff_m1m3")})
    )
    st.dataframe(diff_stats, hide_index=True, use_container_width=True)
