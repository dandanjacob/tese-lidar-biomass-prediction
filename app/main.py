"""
Dashboard — LiDAR Biomass Prediction
Navegação: Início · Mapa · Interseções · Geometria das Parcelas
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

ROOT = Path(__file__).parent.parent

# ── Constantes de cor ──────────────────────────────────────────────────────────
C_BLUE  = "#4a90d9"
C_RED   = "#e84545"
C_LIGHT = "#a8d4f5"
C_PINK  = "#f5a8a8"

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
    gdf_ea["area_ha"]     = gdf_ea.geometry.area / 10_000
    gdf_ea["perimeter_m"] = gdf_ea.geometry.length
    gdf_ea["compacidade"] = (4 * np.pi * gdf_ea.geometry.area) / (gdf_ea["perimeter_m"] ** 2)
    return gdf_ea

@st.cache_data
def load_clipped_stats():
    clipped_dir = ROOT / "data/processed/03_clipped_lidar"
    files = list(clipped_dir.rglob("*.laz"))
    rows = []
    for f in files:
        rows.append({"site": f.parent.name, "plot": f.stem, "size_mb": f.stat().st_size / 1e6})
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["site", "plot", "size_mb"])

@st.cache_data
def best_match(temporal_df):
    return (
        temporal_df.sort_values(["abs_gap", "ano_lidar"], ascending=[True, False])
        .groupby(["nome_area_inventario", "plot_id"], as_index=False)
        .first()
    )


# ── Layout ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LiDAR Biomass — Amazônia",
    page_icon="🌳",
    layout="wide",
)

page = st.sidebar.radio(
    "Navegação",
    ["🏠  Início", "🗺️  Mapa de Cobertura", "📊  Análise de Interseções", "📐  Geometria das Parcelas"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.caption("Dissertação de mestrado · FGV · Estimativa de biomassa da Amazônia por LiDAR")


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: INÍCIO
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
    n_clipped = len(clip["plot"].unique()) if not clip.empty else 0

    st.markdown("### Situação atual do dataset")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Parcelas com LiDAR", n_plots, help="Parcelas inteiramente dentro de um único tile (within)")
    c2.metric("Sites cobertos",     n_sites)
    c3.metric("Tiles utilizados",   n_tiles)
    c4.metric("Parcelas clippadas", n_clipped, help="Arquivos .laz gerados em 03_clipped_lidar/")

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
    bst  = best_match(temp)
    thresholds = [0, 1, 2, 3]
    cols = st.columns(len(thresholds))
    for col, t in zip(cols, thresholds):
        n = (bst["abs_gap"] <= t).sum()
        col.metric(f"|gap| ≤ {t} ano(s)", f"{n} parcelas", f"{100*n//len(bst)}%")


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: MAPA
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🗺️  Mapa de Cobertura":
    st.title("🗺️ Mapa de Cobertura LiDAR × Inventário")
    st.caption("Azul = tiles LiDAR · Vermelho = parcelas com LiDAR (within) · Cinza = parcelas sem cobertura")

    html_path = ROOT / "data/processed/02_intersections/map_intersections.html"
    if html_path.exists():
        components.html(html_path.read_text(), height=620, scrolling=False)
    else:
        st.warning("Mapa não encontrado. Rode `make map-interactive` para gerá-lo.")
        if st.button("Gerar mapa agora"):
            import subprocess
            subprocess.run(["python", "src/plot_intersections_interactive.py"], cwd=ROOT)
            st.rerun()

    raw = load_intersections()
    st.markdown("---")
    st.markdown("### Parcelas por site de inventário")
    per_site = (
        raw.groupby("inventory_file")["plot_id"]
        .nunique()
        .reset_index()
        .rename(columns={"inventory_file": "site", "plot_id": "parcelas"})
        .sort_values("parcelas", ascending=True)
    )
    per_site["site"] = per_site["site"].str.replace("_inventory_plots|_inventory", "", regex=True)
    fig = px.bar(
        per_site, x="parcelas", y="site", orientation="h",
        color_discrete_sequence=[C_BLUE],
        labels={"parcelas": "Parcelas únicas com LiDAR", "site": ""},
    )
    fig.update_layout(height=520, margin=dict(l=0, r=20, t=10, b=40))
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: ANÁLISE DE INTERSEÇÕES
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊  Análise de Interseções":
    st.title("📊 Análise de Interseções")

    temp = load_temporal()
    bst  = best_match(temp)

    # Gap temporal — todas as interseções
    gap_all = (
        temp.drop_duplicates(["nome_area_inventario", "plot_id", "campanha_lidar"])
        .groupby("gap_temporal_anos").size().reset_index(name="n_pares")
        .sort_values("gap_temporal_anos")
    )
    gap_all["categoria"] = gap_all["gap_temporal_anos"].apply(
        lambda g: "Mesmo ano" if g == 0 else ("|gap| ≤ 2" if abs(g) <= 2 else "|gap| > 2")
    )

    # Gap temporal — melhor match
    gap_best = (
        bst.groupby("gap_temporal_anos").size().reset_index(name="n_parcelas")
        .sort_values("gap_temporal_anos")
    )
    gap_best["categoria"] = gap_best["gap_temporal_anos"].apply(
        lambda g: "Mesmo ano" if g == 0 else ("|gap| ≤ 2" if abs(g) <= 2 else "|gap| > 2")
    )

    COLOR_MAP = {"Mesmo ano": C_BLUE, "|gap| ≤ 2": C_LIGHT, "|gap| > 2": C_PINK}

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"Todas as interseções ({len(gap_all['n_pares'].sum())} pares)")
        st.caption("Pares parcela × campanha LiDAR, sem filtro temporal")
        fig = px.bar(
            gap_all, x="gap_temporal_anos", y="n_pares",
            color="categoria", color_discrete_map=COLOR_MAP,
            labels={"gap_temporal_anos": "Gap temporal (anos)", "n_pares": "Pares", "categoria": ""},
            text="n_pares",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, height=380, margin=dict(t=10))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader(f"Melhor match temporal ({len(bst)} parcelas únicas)")
        st.caption("Uma campanha LiDAR por parcela — a de menor gap")
        fig = px.bar(
            gap_best, x="gap_temporal_anos", y="n_parcelas",
            color="categoria", color_discrete_map=COLOR_MAP,
            labels={"gap_temporal_anos": "Gap temporal (anos)", "n_parcelas": "Parcelas", "categoria": ""},
            text="n_parcelas",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=True, height=380, margin=dict(t=10))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("### Parcelas disponíveis por threshold de gap")
    rows = []
    for t in [0, 1, 2, 3]:
        n = (bst["abs_gap"] <= t).sum()
        rows.append({"Threshold": f"≤ {t} ano(s)", "Parcelas": n, "%": f"{100*n//len(bst)}%"})
    st.table(pd.DataFrame(rows))


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: GEOMETRIA DAS PARCELAS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📐  Geometria das Parcelas":
    st.title("📐 Geometria das Parcelas")
    st.caption("Área e formato dos polígonos de inventário que têm cobertura LiDAR (critério within)")

    temp  = load_temporal()
    bst   = best_match(temp)
    plots = load_plot_geometries()

    all_pairs = (
        temp.drop_duplicates(["nome_area_inventario", "plot_id", "campanha_lidar"])
        .merge(plots.rename(columns={"site": "nome_area_inventario"}),
               on=["nome_area_inventario", "plot_id"], how="inner")
    )
    best_plots = (
        bst.merge(plots.rename(columns={"site": "nome_area_inventario"}),
                  on=["nome_area_inventario", "plot_id"], how="inner")
    )

    tab1, tab2 = st.tabs(["📏 Área (ha)", "🔷 Compacidade"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            fig = px.histogram(
                all_pairs, x="area_ha", nbins=30,
                color_discrete_sequence=[C_BLUE],
                labels={"area_ha": "Área (ha)", "count": "Frequência"},
                title=f"Todas as interseções ({len(all_pairs)} pares)",
            )
            med = all_pairs["area_ha"].median()
            fig.add_vline(x=med, line_dash="dash", line_color=C_RED,
                          annotation_text=f"Mediana: {med:.2f} ha")
            fig.update_layout(height=380, margin=dict(t=40))
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.histogram(
                best_plots, x="area_ha", nbins=30,
                color_discrete_sequence=[C_RED],
                labels={"area_ha": "Área (ha)", "count": "Frequência"},
                title=f"Melhor match temporal ({len(best_plots)} parcelas)",
            )
            med = best_plots["area_ha"].median()
            fig.add_vline(x=med, line_dash="dash", line_color="#2c3e50",
                          annotation_text=f"Mediana: {med:.2f} ha")
            fig.update_layout(height=380, margin=dict(t=40))
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.caption("Compacidade = 4π × área / perímetro² · Círculo=1.0 · Quadrado≈0.79 · Formas irregulares < 0.5")
        col1, col2 = st.columns(2)
        with col1:
            fig = px.histogram(
                all_pairs, x="compacidade", nbins=30,
                color_discrete_sequence=[C_BLUE],
                labels={"compacidade": "Compacidade", "count": "Frequência"},
                title=f"Todas as interseções ({len(all_pairs)} pares)",
            )
            med = all_pairs["compacidade"].median()
            fig.add_vline(x=med, line_dash="dash", line_color=C_RED,
                          annotation_text=f"Mediana: {med:.3f}")
            fig.add_vline(x=np.pi/4, line_dash="dot", line_color="#888",
                          annotation_text="Quadrado (0.785)")
            fig.update_layout(height=380, margin=dict(t=40))
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.histogram(
                best_plots, x="compacidade", nbins=30,
                color_discrete_sequence=[C_RED],
                labels={"compacidade": "Compacidade", "count": "Frequência"},
                title=f"Melhor match temporal ({len(best_plots)} parcelas)",
            )
            med = best_plots["compacidade"].median()
            fig.add_vline(x=med, line_dash="dash", line_color="#2c3e50",
                          annotation_text=f"Mediana: {med:.3f}")
            fig.add_vline(x=np.pi/4, line_dash="dot", line_color="#888",
                          annotation_text="Quadrado (0.785)")
            fig.update_layout(height=380, margin=dict(t=40))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Parcelas mais irregulares**")
            st.dataframe(
                best_plots.nsmallest(5, "compacidade")
                [["nome_area_inventario", "plot_id", "area_ha", "compacidade"]]
                .rename(columns={"nome_area_inventario": "site"})
                .round(3),
                hide_index=True
            )
        with col2:
            st.markdown("**Parcelas mais compactas**")
            st.dataframe(
                best_plots.nlargest(5, "compacidade")
                [["nome_area_inventario", "plot_id", "area_ha", "compacidade"]]
                .rename(columns={"nome_area_inventario": "site"})
                .round(3),
                hide_index=True
            )
