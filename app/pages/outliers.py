"""Outliers de geometria — parcelas de forma/área atípica.

Cada parcela é um polígono. As que têm compacidade muito baixa (faixas finas e
compridas) ou área muito grande são as que mais sofrem com erro de borda no recorte
do LiDAR e são candidatas a refatoração (subdividir / segmentar / excluir). Esta
página permite inspecionar a forma de cada outlier e seus números.
"""

import pandas as pd
import streamlit as st

from lib import data
from lib.charts import plot_shape
from lib.i18n import t, with_acronyms
from lib.theme import C_RED

st.title(t("outliers.title"))
st.caption(with_acronyms(t("outliers.caption")), unsafe_allow_html=True)
st.markdown(t("outliers.intro"))

q = data.load_plot_quality()
q = q[q["area_ha"].notna() & q["compacidade"].notna()].copy()
q["site_short"] = q["site"].str.replace(r"_inventory_plots|_inventory", "", regex=True)

# ── Critério de outlier (ajustável) ──
st.markdown(f"#### {t('outliers.criteria_title')}")
c1, c2 = st.columns(2)
comp_max = c1.slider(t("outliers.comp_thr"), 0.0, 0.785, 0.40, 0.01,
                     help=t("outliers.comp_help"))
area_cap = round(float(q["area_ha"].max()), 2)
area_min = c2.slider(t("outliers.area_thr"), 0.0, area_cap,
                     min(0.5, area_cap), 0.05, help=t("outliers.area_help"))

out = q[(q["compacidade"] < comp_max) | (q["area_ha"] > area_min)].copy()
out = out.sort_values("compacidade").reset_index(drop=True)
st.markdown(t("outliers.count", n=len(out), total=len(q)))

if out.empty:
    st.info(t("outliers.none"))
    st.stop()

# ── Inspeção de um outlier ──
st.markdown("---")
st.markdown(f"### {t('outliers.inspect_title')}")


def _label(i):
    r = out.loc[i]
    return (f"{r.site_short} · {r.plot_id}  —  "
            f"{t('outliers.compactness')} {r.compacidade:.3f} · "
            f"{r.area_ha * 1e4:,.0f} m²")


choice = st.selectbox(t("outliers.pick"), options=list(out.index),
                      format_func=_label)
r = out.loc[choice]

col_shape, col_help = st.columns([3, 2])
with col_shape:
    st.plotly_chart(plot_shape(r.geometry, C_RED, height=420),
                    use_container_width=True)
with col_help:
    st.markdown(t("outliers.shape_note"))

# ── Métricas da parcela escolhida ──
m = st.columns(5)
m[0].metric(t("outliers.m_dims"), f"{r.width_m:.0f} × {r.length_m:.0f} m",
            help=t("outliers.m_dims_help"))
m[1].metric(t("outliers.m_area"), f"{r.area_ha * 1e4:,.0f} m²",
            help=f"{r.area_ha:.3f} ha")
m[2].metric(t("outliers.m_comp"), f"{r.compacidade:.3f}")
m[3].metric(t("outliers.m_trees"),
            "—" if pd.isna(r.n_arvores) else f"{int(r.n_arvores)}")
m[4].metric(t("outliers.m_pos"),
            "—" if pd.isna(r.pct_pos) else f"{r.pct_pos:.0f}%",
            help=t("outliers.m_pos_help"))

# ── Tabela com todos os outliers ──
st.markdown("---")
st.markdown(f"### {t('outliers.table_title')}")

tbl = out.assign(
    **{
        t("outliers.col_site"): out["site_short"],
        t("outliers.col_plot"): out["plot_id"].astype(str),
        t("outliers.col_dims"): (out["width_m"].round(0).astype(int).astype(str)
                                 + " × " + out["length_m"].round(0).astype(int).astype(str)),
        t("outliers.col_area"): (out["area_ha"] * 1e4).round(0),
        t("outliers.col_comp"): out["compacidade"].round(3),
        t("outliers.col_trees"): out["n_arvores"],
        t("outliers.col_pos"): out["pct_pos"].round(0),
    }
)[[t("outliers.col_site"), t("outliers.col_plot"), t("outliers.col_dims"),
   t("outliers.col_area"), t("outliers.col_comp"), t("outliers.col_trees"),
   t("outliers.col_pos")]]

st.dataframe(tbl, hide_index=True, use_container_width=True)
st.caption(t("outliers.table_caption"))
