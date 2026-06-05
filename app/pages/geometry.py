"""Geometria das parcelas — área e compacidade."""

import streamlit as st

from lib import data
from lib.charts import hist_with_stats, plot_shape
from lib.i18n import md, t, with_acronyms
from lib.theme import C_BLUE, C_RED

st.title(t("geometry.title"))
st.caption(with_acronyms(t("geometry.caption")), unsafe_allow_html=True)
st.markdown(t("geometry.intro"))

with st.expander(t("geometry.help_expander")):
    st.markdown(with_acronyms(md("geometry_help")), unsafe_allow_html=True)

temp = data.load_temporal()
plots = data.load_plot_geometries()
bst_df = data.best_match(temp)

best_plots = (
    bst_df.merge(plots.rename(columns={"site": "nome_area_inventario"}),
                 on=["nome_area_inventario", "plot_id"], how="inner")
)

tab1, tab2 = st.tabs([t("geometry.tab_area"), t("geometry.tab_compactness")])

with tab1:
    st.plotly_chart(
        hist_with_stats(best_plots, "area_ha", C_RED,
                        t("geometry.area_title", n=len(best_plots)),
                        t("geometry.area_xlabel"), bin_size=0.1),
        use_container_width=True,
    )
    st.markdown(t("geometry.area_desc"))
    c1, c2, c3 = st.columns(3)
    c1.metric(t("geometry.area_min"), f"{best_plots.area_ha.min():.3f} ha")
    c2.metric(t("geometry.area_median"), f"{best_plots.area_ha.median():.3f} ha")
    c3.metric(t("geometry.area_max"), f"{best_plots.area_ha.max():.2f} ha")

with tab2:
    st.caption(t("geometry.compactness_caption"))
    st.plotly_chart(
        hist_with_stats(best_plots, "compacidade", C_BLUE,
                        t("geometry.compactness_title", n=len(best_plots)),
                        t("geometry.compactness_xlabel"), bin_size=0.05),
        use_container_width=True,
    )
    st.markdown(t("geometry.compactness_desc"))

    # ── Exemplos de formas extremas ──
    st.markdown("---")
    st.markdown(f"### {t('geometry.shapes_title')}")
    st.markdown(t("geometry.shapes_desc"))

    # Usa apenas polígonos de parte única: o multipolígono espalhado (ex. JAM "0")
    # tem compacidade baixa por ser disjunto, não por ser uma forma estreita/comprida.
    single = best_plots[best_plots.geometry.apply(lambda g: g.geom_type) == "Polygon"]
    elong = single.nsmallest(1, "compacidade").iloc[0]
    square = single.nlargest(1, "compacidade").iloc[0]
    # mesma escala nos dois: metade do maior lado entre as duas formas (+10%)
    half = 0
    for g in (elong.geometry, square.geometry):
        minx, miny, maxx, maxy = g.bounds
        half = max(half, (maxx - minx) / 2, (maxy - miny) / 2)
    rng = [-half * 1.1, half * 1.1]

    s1, s2 = st.columns(2)
    with s1:
        st.markdown(f"**{t('geometry.shape_elongated', c=elong.compacidade)}**")
        st.plotly_chart(plot_shape(elong.geometry, C_RED, axis_range=rng),
                        use_container_width=True)
    with s2:
        st.markdown(f"**{t('geometry.shape_square', c=square.compacidade)}**")
        st.plotly_chart(plot_shape(square.geometry, C_BLUE, axis_range=rng),
                        use_container_width=True)

    st.markdown("---")
    col1, col2 = st.columns(2)
    cols = ["nome_area_inventario", "plot_id", "area_ha", "compacidade"]
    with col1:
        st.markdown(f"**{t('geometry.most_irregular')}**")
        st.dataframe(
            best_plots.nsmallest(5, "compacidade")[cols]
            .rename(columns={"nome_area_inventario": t("geometry.col_site")})
            .round(3), hide_index=True,
        )
    with col2:
        st.markdown(f"**{t('geometry.most_compact')}**")
        st.dataframe(
            best_plots.nlargest(5, "compacidade")[cols]
            .rename(columns={"nome_area_inventario": t("geometry.col_site")})
            .round(3), hide_index=True,
        )
