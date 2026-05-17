"""
Dashboard — LiDAR Biomass Prediction
Navegação: Início · Mapa · Interseções · Geometria · Nuvem de Pontos
"""

import geopandas as gpd
import laspy
import numpy as np
import pandas as pd
import folium
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

ROOT = Path(__file__).parent.parent

C_BLUE  = "#4a90d9"
C_RED   = "#e84545"
C_LIGHT = "#a8d4f5"
C_PINK  = "#f5a8a8"
COLOR_MAP = {"Mesmo ano": C_BLUE, "|gap| ≤ 2": C_LIGHT, "|gap| > 2": C_PINK}

# ── Dados ──────────────────────────────────────────────────────────────────────
@st.cache_data
def load_intersections():
    return pd.read_csv(ROOT / "data/processed/02_intersections/lidar_inventory_intersections.csv")

@st.cache_data
def load_temporal():
    df = pd.read_csv(ROOT / "data/processed/02_intersections/intersections_temporal.csv")
    df["campanha_lidar"] = df["nome_area_lidar"].str.extract(r"^(.+)_\d+\.laz$")[0]
    df["abs_gap"] = df["gap_temporal_anos"].abs()
    return df

@st.cache_data
def load_plot_geometries():
    EQUAL_AREA = "+proj=aea +lat_1=-5 +lat_2=-42 +lat_0=-32 +lon_0=-60 +datum=WGS84 +units=m +no_defs"
    kml_dir = ROOT / "data/processed/01_kml"
    frames = []
    for kml in kml_dir.glob("*.kml"):
        if "lidar" in kml.name:
            continue
        try:
            gdf = gpd.read_file(kml, driver="KML").set_crs("EPSG:4326")
            gdf["site"]    = kml.stem
            gdf["plot_id"] = gdf["Name"].astype(str)
            frames.append(gdf[["site", "plot_id", "geometry"]])
        except Exception:
            pass
    gdf_all = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
    gdf_ea  = gdf_all.to_crs(EQUAL_AREA).dissolve(by=["site", "plot_id"]).reset_index()
    # filtra geometrias degeneradas (LineString, GeometryCollection) que não têm área
    gdf_ea = gdf_ea[gdf_ea.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    gdf_ea["area_ha"]     = gdf_ea.geometry.area / 10_000
    gdf_ea["perimeter_m"] = gdf_ea.geometry.length
    gdf_ea["compacidade"] = (4 * np.pi * gdf_ea.geometry.area) / (gdf_ea["perimeter_m"] ** 2)
    return gdf_ea

@st.cache_data
def load_clipped_stats():
    clipped_dir = ROOT / "data/processed/03_clipped_lidar"
    files = list(clipped_dir.rglob("*.laz"))
    rows = [{"site": f.parent.name, "plot": f.stem, "path": str(f),
             "size_mb": f.stat().st_size / 1e6} for f in files]
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["site","plot","path","size_mb"])

@st.cache_data
def best_match(temporal_df):
    return (
        temporal_df.sort_values(["abs_gap", "ano_lidar"], ascending=[True, False])
        .groupby(["nome_area_inventario", "plot_id"], as_index=False)
        .first()
    )

def merged_geo(temporal_df, plots_geo):
    bst = best_match(temporal_df)
    return (
        bst.merge(plots_geo.rename(columns={"site": "nome_area_inventario"}),
                  on=["nome_area_inventario", "plot_id"], how="inner")
    )

def hist_with_stats(df, col, color, title, xlabel):
    """Histograma plotly com linhas de média e mediana bem posicionadas."""
    mean_val   = df[col].mean()
    median_val = df[col].median()
    fig = px.histogram(df, x=col, nbins=30, color_discrete_sequence=[color],
                       labels={col: xlabel, "count": "Frequência"})
    fig.add_vline(x=mean_val,   line_dash="solid", line_color="#c0392b", line_width=2)
    fig.add_vline(x=median_val, line_dash="dash",  line_color="#2c3e50", line_width=2)
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines",
                             line=dict(color="#c0392b", width=2, dash="solid"),
                             name=f"Média: {mean_val:.3f}"))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines",
                             line=dict(color="#2c3e50", width=2, dash="dash"),
                             name=f"Mediana: {median_val:.3f}"))
    fig.update_layout(title=title, height=380, margin=dict(t=50),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig

# ── Layout ─────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="LiDAR Biomass — Amazônia", page_icon="🌳", layout="wide")

page = st.sidebar.radio(
    "Navegação",
    ["🏠  Início", "🗺️  Mapa de Cobertura", "📊  Análise de Interseções",
     "📐  Geometria das Parcelas", "☁️  Nuvem de Pontos"],
    label_visibility="collapsed",
)
st.sidebar.markdown("---")
st.sidebar.caption("Dissertação de mestrado · FGV\nEstimativa de biomassa da Amazônia por LiDAR")


# ══════════════════════════════════════════════════════════════════════════════
# INÍCIO
# ══════════════════════════════════════════════════════════════════════════════
if page == "🏠  Início":
    st.title("🌳 LiDAR Biomass Prediction")
    st.markdown("Estimativa de biomassa da floresta amazônica a partir de dados LiDAR (NASA/ORNL) cruzados com inventários florestais de campo.")

    raw  = load_intersections()
    temp = load_temporal()
    clip = load_clipped_stats()

    n_plots   = raw.groupby(["inventory_file", "plot_id"]).ngroups
    n_sites   = raw["inventory_file"].nunique()
    n_tiles   = raw["laz_file"].nunique()
    n_clipped = clip["plot"].nunique() if not clip.empty else 0

    st.markdown("### Situação atual do dataset")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Parcelas com LiDAR",  n_plots,   help="Inteiramente dentro de um único tile (within)")
    c2.metric("Sites cobertos",      n_sites)
    c3.metric("Tiles utilizados",    n_tiles)
    c4.metric("Parcelas clippadas",  n_clipped, help="Arquivos .laz em 03_clipped_lidar/")

    st.markdown("---")
    st.markdown("### Pipeline")
    st.code("""
data/raw/inventory/   ← inventários de campo (.csv, .kmz)
data/raw/lidar/       ← tiles LiDAR (.laz)  NASA/ORNL DOI: 10.3334/ORNLDAAC/1515
        │
        ▼  src/extract_kml.sh          [✓ concluído]
data/processed/01_kml/

        ▼  src/find_intersections.py   [✓ concluído]  critério: within
data/processed/02_intersections/

        ▼  src/clip_lidar_to_plots.py  [⏳ em andamento]
data/processed/03_clipped_lidar/

        ▼  extração de métricas LiDAR  [a implementar]
        ▼  modelagem de biomassa       [a implementar]
    """, language="text")

    st.markdown("---")
    st.markdown("### Gap temporal (LiDAR × inventário) — melhor match")
    bst = best_match(temp)
    cols = st.columns(4)
    for col, t in zip(cols, [0, 1, 2, 3]):
        n = int((bst["abs_gap"] <= t).sum())
        cols[t].metric(f"|gap| ≤ {t} ano(s)", f"{n}", f"{100*n//len(bst)}%")


# ══════════════════════════════════════════════════════════════════════════════
# MAPA
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🗺️  Mapa de Cobertura":
    st.title("🗺️ Mapa de Cobertura LiDAR × Inventário")

    raw  = load_intersections()
    temp = load_temporal()

    view = st.radio(
        "Visualizar",
        ["Tudo (tiles + parcelas com e sem LiDAR)", "Apenas interseções (parcelas com LiDAR)"],
        horizontal=True,
    )

    intersected_keys = set(zip(raw["inventory_file"], raw["plot_id"].astype(str)))

    @st.cache_data
    def build_map(show_all: bool) -> str:
        from geodatasets import get_path
        from shapely.geometry import box as sbox

        kml_dir = ROOT / "data/processed/01_kml"
        lidar_csv_dir = sorted((ROOT / "data/raw/lidar").glob("LiDAR_Forest_Inventory_Brazil_*"))[0]
        lidar_meta = pd.read_csv(lidar_csv_dir / "cms_brazil_lidar_tile_inventory.csv")

        m = folium.Map(location=[-5.5, -57.0], zoom_start=5, tiles="CartoDB positron")

        if show_all:
            tiles_used = set(raw["laz_file"])
            used_meta  = lidar_meta[lidar_meta["filename"].isin(tiles_used)]
            tile_group = folium.FeatureGroup(name="Tiles LiDAR (199)", show=True)
            for r in used_meta.itertuples():
                folium.Rectangle(
                    bounds=[[r.min_lat, r.min_lon], [r.max_lat, r.max_lon]],
                    color="#4a90d9", fill=True, fill_opacity=0.12, weight=0.7,
                    tooltip=r.filename,
                ).add_to(tile_group)
            tile_group.add_to(m)

        plot_group_yes = folium.FeatureGroup(name="Parcelas com LiDAR", show=True)
        plot_group_no  = folium.FeatureGroup(name="Parcelas sem LiDAR",  show=show_all)

        # Carrega todos os KMLs e dissolve por (site, plot_id) para ter um centroide por parcela
        frames = []
        for kml in kml_dir.glob("*.kml"):
            if "lidar" in kml.name:
                continue
            try:
                gdf = gpd.read_file(kml, driver="KML").set_crs("EPSG:4326")
                gdf["site"]    = kml.stem
                gdf["plot_id"] = gdf["Name"].astype(str)
                frames.append(gdf[["site", "plot_id", "geometry"]])
            except Exception:
                pass

        all_plots = (
            gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
            .dissolve(by=["site", "plot_id"]).reset_index()
        )

        for _, row in all_plots.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            has = (row["site"], row["plot_id"]) in intersected_keys
            if not has and not show_all:
                continue
            grp        = plot_group_yes if has else plot_group_no
            pin_color  = "red" if has else "gray"
            poly_color = "#e84545" if has else "#aaaaaa"
            site_short = row["site"].replace("_inventory_plots", "").replace("_inventory", "")
            tooltip    = f"{site_short} / plot {row['plot_id']}"
            c = geom.centroid

            # Pin — visível em qualquer zoom
            folium.Marker(
                location=[c.y, c.x],
                icon=folium.Icon(color=pin_color, icon="map-marker", prefix="fa"),
                tooltip=tooltip,
            ).add_to(grp)

            # Polígono — visível ao aproximar
            try:
                geoms = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
                for part in geoms:
                    coords = [[c2[1], c2[0]] for c2 in part.exterior.coords]
                    folium.Polygon(
                        locations=coords, color=poly_color, fill=True,
                        fill_opacity=0.5, weight=1.5, tooltip=tooltip,
                    ).add_to(grp)
            except Exception:
                pass

        plot_group_yes.add_to(m)
        if show_all:
            plot_group_no.add_to(m)
        folium.LayerControl(collapsed=False).add_to(m)
        return m._repr_html_()

    show_all = "sem LiDAR" in view
    components.html(build_map(show_all), height=580, scrolling=False)

    st.markdown("---")
    per_site = (
        raw.groupby("inventory_file")["plot_id"].nunique().reset_index()
        .rename(columns={"inventory_file": "site", "plot_id": "parcelas"})
        .sort_values("parcelas", ascending=True)
    )
    per_site["site"] = per_site["site"].str.replace("_inventory_plots|_inventory", "", regex=True)
    fig = px.bar(per_site, x="parcelas", y="site", orientation="h",
                 color_discrete_sequence=[C_BLUE],
                 labels={"parcelas": "Parcelas com LiDAR", "site": ""},
                 title="Parcelas por site de inventário")
    fig.update_layout(height=500, margin=dict(l=0, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# ANÁLISE DE INTERSEÇÕES
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊  Análise de Interseções":
    st.title("📊 Análise de Interseções")

    temp = load_temporal()
    bst  = best_match(temp)

    def gap_category(g):
        return "Mesmo ano" if g == 0 else ("|gap| ≤ 2" if abs(g) <= 2 else "|gap| > 2")

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

    total_all  = int(gap_all["n_pares"].sum())
    total_best = int(gap_best["n_parcelas"].sum())

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"Todas as interseções — {total_all} pares")
        st.caption("Pares parcela × campanha LiDAR, sem filtro temporal")
        fig = px.bar(gap_all, x="gap_temporal_anos", y="n_pares",
                     color="categoria", color_discrete_map=COLOR_MAP,
                     text="n_pares",
                     labels={"gap_temporal_anos": "Gap (anos)", "n_pares": "Pares", "categoria": ""})
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, height=380, margin=dict(t=10))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader(f"Melhor match temporal — {total_best} parcelas únicas")
        st.caption("Uma campanha LiDAR por parcela — a de menor gap")
        fig = px.bar(gap_best, x="gap_temporal_anos", y="n_parcelas",
                     color="categoria", color_discrete_map=COLOR_MAP,
                     text="n_parcelas",
                     labels={"gap_temporal_anos": "Gap (anos)", "n_parcelas": "Parcelas", "categoria": ""})
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=True, height=380, margin=dict(t=10))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("### Parcelas disponíveis por threshold de gap")
    rows = [{"Threshold": f"≤ {t} ano(s)",
             "Parcelas": int((bst["abs_gap"] <= t).sum()),
             "%": f"{100*(bst['abs_gap'] <= t).sum()//len(bst)}%"}
            for t in [0, 1, 2, 3]]
    st.table(pd.DataFrame(rows))


# ══════════════════════════════════════════════════════════════════════════════
# GEOMETRIA
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📐  Geometria das Parcelas":
    st.title("📐 Geometria das Parcelas")
    st.caption("Apenas parcelas com cobertura LiDAR (critério within) e geometrias de polígono válidas.")

    with st.expander("ℹ️ Média vs. Mediana — qual usar?"):
        st.markdown("""
- **Média**: intuitiva, mas sensível a outliers. Uma parcela muito grande puxa a média para cima.
- **Mediana**: valor central — 50% das parcelas estão acima e 50% abaixo. Mais representativa quando há distribuição assimétrica.

Para área de parcelas florestais, a distribuição tende a ser assimétrica (algumas bem maiores que o padrão), por isso a mediana é mais informativa. Ambas são exibidas nos gráficos.
        """)

    temp  = load_temporal()
    plots = load_plot_geometries()
    bst_df = best_match(temp)

    best_plots = (
        bst_df.merge(plots.rename(columns={"site": "nome_area_inventario"}),
                     on=["nome_area_inventario", "plot_id"], how="inner")
    )

    tab1, tab2 = st.tabs(["📏 Área (ha)", "🔷 Compacidade"])

    with tab1:
        st.plotly_chart(
            hist_with_stats(best_plots, "area_ha", C_RED,
                            f"Distribuição de área — {len(best_plots)} parcelas (melhor match temporal)",
                            "Área (ha)"),
            use_container_width=True
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Mínima",  f"{best_plots.area_ha.min():.3f} ha")
        c2.metric("Mediana", f"{best_plots.area_ha.median():.3f} ha")
        c3.metric("Máxima",  f"{best_plots.area_ha.max():.2f} ha")

    with tab2:
        st.caption("Compacidade = 4π × área / perímetro²  ·  Círculo = 1.0  ·  Quadrado ≈ 0.785  ·  Formas irregulares < 0.5")
        st.plotly_chart(
            hist_with_stats(best_plots, "compacidade", C_BLUE,
                            f"Distribuição de compacidade — {len(best_plots)} parcelas (melhor match temporal)",
                            "Compacidade"),
            use_container_width=True
        )

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Parcelas mais irregulares (menor compacidade)**")
            st.dataframe(
                best_plots.nsmallest(5, "compacidade")
                [["nome_area_inventario", "plot_id", "area_ha", "compacidade"]]
                .rename(columns={"nome_area_inventario": "site"})
                .round(3), hide_index=True
            )
        with col2:
            st.markdown("**Parcelas mais compactas (maior compacidade)**")
            st.dataframe(
                best_plots.nlargest(5, "compacidade")
                [["nome_area_inventario", "plot_id", "area_ha", "compacidade"]]
                .rename(columns={"nome_area_inventario": "site"})
                .round(3), hide_index=True
            )


# ══════════════════════════════════════════════════════════════════════════════
# NUVEM DE PONTOS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "☁️  Nuvem de Pontos":
    st.title("☁️ Visualizador de Nuvem de Pontos")
    st.caption("Pontos clippados para cada parcela de inventário. Coloridos por altura (Z).")

    clip = load_clipped_stats()
    if clip.empty:
        st.warning("Nenhum arquivo .laz clippado encontrado em `data/processed/03_clipped_lidar/`. Rode `make clip` primeiro.")
        st.stop()

    sites = sorted(clip["site"].unique())
    col1, col2 = st.columns([2, 1])
    with col1:
        site = st.selectbox("Site", sites)
    with col2:
        plots_available = sorted(clip[clip["site"] == site]["plot"].tolist())
        plot = st.selectbox("Parcela", plots_available)

    max_pts = st.slider("Máximo de pontos exibidos", 5_000, 100_000, 30_000, step=5_000,
                        help="Subamostrado aleatoriamente. Mais pontos = mais lento.")

    laz_path = Path(clip[(clip["site"] == site) & (clip["plot"] == plot)]["path"].values[0])

    if not laz_path.exists():
        st.error(f"Arquivo não encontrado: {laz_path}")
        st.stop()

    with st.spinner("Carregando nuvem de pontos..."):
        las = laspy.read(laz_path)
        n_total = len(las.x)
        idx = np.random.choice(n_total, min(max_pts, n_total), replace=False)
        x, y, z = np.array(las.x)[idx], np.array(las.y)[idx], np.array(las.z)[idx]
        # centraliza pra melhor visualização
        x -= x.mean(); y -= y.mean()

    st.info(f"**{n_total:,}** pontos no arquivo · exibindo **{len(idx):,}** ({100*len(idx)//n_total}%)")

    fig = go.Figure(data=[go.Scatter3d(
        x=x, y=y, z=z,
        mode="markers",
        marker=dict(
            size=1.5,
            color=z,
            colorscale="Viridis",
            colorbar=dict(title="Altura (m)"),
            opacity=0.85,
        ),
    )])
    fig.update_layout(
        height=620,
        margin=dict(l=0, r=0, t=10, b=0),
        scene=dict(
            xaxis_title="X (m)", yaxis_title="Y (m)", zaxis_title="Z — altura (m)",
            aspectmode="data",
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Altura mínima", f"{z.min():.1f} m")
    c2.metric("Altura mediana", f"{np.median(z):.1f} m")
    c3.metric("Altura máxima", f"{z.max():.1f} m")
