"""Visualizador 3D de nuvem de pontos LiDAR + biomassa da parcela."""

from pathlib import Path

import laspy
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from lib import data
from lib.i18n import md, t, with_acronyms
from lib.theme import C_BLUE, C_LIGHT, C_RED

st.title(t("pointcloud.title"))
st.caption(with_acronyms(t("pointcloud.caption")), unsafe_allow_html=True)

clip = data.load_clipped_stats()
if clip.empty:
    st.warning(t("pointcloud.no_data"))
    st.stop()

sites = sorted(clip["site"].unique())
col1, col2 = st.columns([2, 1])
with col1:
    site = st.selectbox(t("pointcloud.site"), sites)
with col2:
    plots_available = sorted(clip[clip["site"] == site]["plot"].tolist())
    plot = st.selectbox(t("pointcloud.plot"), plots_available)

max_pts = st.slider(t("pointcloud.max_points"), 5_000, 100_000, 30_000, step=5_000,
                    help=t("pointcloud.max_points_help"))

laz_path = Path(clip[(clip["site"] == site) & (clip["plot"] == plot)]["path"].values[0])

if not laz_path.exists():
    st.error(t("pointcloud.file_not_found", path=laz_path))
    st.stop()

with st.spinner(t("pointcloud.loading")):
    las = laspy.read(laz_path)
    n_total = len(las.x)
    idx = np.random.choice(n_total, min(max_pts, n_total), replace=False)
    x, y, z = np.array(las.x)[idx], np.array(las.y)[idx], np.array(las.z)[idx]
    # centraliza pra melhor visualização
    x -= x.mean()
    y -= y.mean()

st.info(t("pointcloud.info_points", total=n_total, shown=len(idx), pct=100 * len(idx) // n_total))

fig = go.Figure(data=[go.Scatter3d(
    x=x, y=y, z=z, mode="markers",
    marker=dict(size=1.5, color=z, colorscale="Viridis",
                colorbar=dict(title=t("pointcloud.colorbar_height")), opacity=0.85),
)])
fig.update_layout(
    height=620, margin=dict(l=0, r=0, t=10, b=0),
    scene=dict(xaxis_title="X (m)", yaxis_title="Y (m)", zaxis_title=t("pointcloud.axis_z"),
               aspectmode="data"),
)
st.plotly_chart(fig, use_container_width=True)

c1, c2, c3 = st.columns(3)
c1.metric(t("pointcloud.height_min"), f"{z.min():.1f} m")
c2.metric(t("pointcloud.height_median"), f"{np.median(z):.1f} m")
c3.metric(t("pointcloud.height_max"), f"{z.max():.1f} m")

# Dimensões da parcela (largura × comprimento) a partir do polígono do inventário
geo = data.load_plot_geometries()
pid = plot.replace("plot_", "")
grow = geo[(geo["site"] == site) & (geo["plot_id"] == pid)]
if not grow.empty:
    try:
        mrr = grow.geometry.iloc[0].minimum_rotated_rectangle
        xs, ys = mrr.exterior.coords.xy
        edges = [((xs[i] - xs[i + 1]) ** 2 + (ys[i] - ys[i + 1]) ** 2) ** 0.5 for i in range(4)]
        width, length = sorted([edges[0], edges[1]])
        d1, d2, d3 = st.columns(3)
        d1.metric(t("pointcloud.plot_width"), f"{width:.1f} m")
        d2.metric(t("pointcloud.plot_length"), f"{length:.1f} m")
        d3.metric(t("pointcloud.plot_area_poly"), f"{grow.area_ha.iloc[0]:.3f} ha")
        st.caption(t("pointcloud.dims_caption"))
    except Exception:
        pass

st.markdown("---")
st.markdown(f"### {t('pointcloud.biomass_section')}")

with st.expander(t("formulas.expander")):
    st.markdown(with_acronyms(md("formulas_body")), unsafe_allow_html=True)

bio = data.load_biomass_summary()
plot_id_num = plot.replace("plot_", "")
bio_row = bio[(bio["site"] == site) & (bio["plot_id"] == plot_id_num)] if not bio.empty else bio

if bio_row.empty:
    st.info(t("pointcloud.biomass_unavailable"))
else:
    r = bio_row.iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric(t("formulas.m1_short"), f"{r['agb_m1_Mg_ha']:.1f} Mg/ha", help=t("formulas.m1_help"))
    c2.metric(t("formulas.m2_short"), f"{r['agb_m2_Mg_ha']:.1f} Mg/ha", help=t("formulas.m2_help"))
    c3.metric(t("formulas.m3_short"), f"{r['agb_m3_Mg_ha']:.1f} Mg/ha", help=t("formulas.m3_help"))

    formulas = [t("formulas.m1_short"), t("formulas.m2_short"), t("formulas.m3_short")]
    values = [r["agb_m1_Mg_ha"], r["agb_m2_Mg_ha"], r["agb_m3_Mg_ha"]]
    fig_bio = go.Figure(go.Bar(
        x=formulas, y=values, marker_color=[C_BLUE, C_LIGHT, C_RED],
        text=[f"{v:.1f}" for v in values], textposition="outside",
    ))
    fig_bio.update_layout(title=t("pointcloud.biomass_chart_title"),
                          yaxis_title=t("pointcloud.biomass_yaxis"),
                          height=320, margin=dict(t=50, b=20), showlegend=False)
    st.plotly_chart(fig_bio, use_container_width=True)

    extra_cols = st.columns(3)
    extra_cols[0].metric(t("pointcloud.trees_alive"), int(r["n_arvores_vivas"]))
    extra_cols[1].metric(t("pointcloud.plot_area"), f"{r['area_ha']:.3f} ha")
    extra_cols[2].metric(t("pointcloud.density_mean"), f"{r['rho_w_m3_mean']:.3f} g/cm³")
