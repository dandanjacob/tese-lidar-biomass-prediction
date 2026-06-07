"""Mapa de cobertura LiDAR × inventário."""

import folium
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from lib import data
from lib.i18n import t

st.title(t("map.title"))

st.markdown(t("map.intro_map"))

raw = data.load_intersections()

# Categoria de aproveitamento por parcela (verde/vermelho/cinza) — mesma do gráfico
# "O que chega aos modelos" e do funil de treino.
USABILITY = data.plot_usability()

# Estilo por categoria: (cor do pin folium, cor do polígono)
CAT_STYLE = {
    "green": ("green", "#2e9e5b"),
    "red":   ("red",   "#e84545"),
    "gray":  ("gray",  "#aaaaaa"),
}


@st.cache_data
def build_map(cache_key: float, layer_tiles: str, lbl_green: str, lbl_red: str,
              lbl_gray: str, tooltip_tpl: str) -> str:
    # cache_key entra só como chave de cache: soma os mtimes de interseções, biomassa
    # e clips (+ código), então o mapa recolore quando QUALQUER um deles é regerado
    # (senão as cores verde/vermelho/cinza ficariam presas na versão antiga).
    lidar_csv_dir = sorted((data.ROOT / "data/raw/lidar").glob("LiDAR_Forest_Inventory_Brazil_*"))[0]
    lidar_meta = pd.read_csv(lidar_csv_dir / "cms_brazil_lidar_tile_inventory.csv")

    m = folium.Map(location=[-5.5, -57.0], zoom_start=5, tiles="CartoDB positron")

    # Tiles LiDAR utilizados — camada alternável pelo controle de camadas
    tiles_used = set(raw["laz_file"])
    used_meta = lidar_meta[lidar_meta["filename"].isin(tiles_used)]
    tile_group = folium.FeatureGroup(name=f"{layer_tiles} ({len(used_meta)})", show=True)
    for r in used_meta.itertuples():
        folium.Rectangle(
            bounds=[[r.min_lat, r.min_lon], [r.max_lat, r.max_lon]],
            color="#4a90d9", fill=True, fill_opacity=0.12, weight=0.7,
            tooltip=r.filename,
        ).add_to(tile_group)
    tile_group.add_to(m)

    # Uma marcação por parcela (plot_id corrigido; partes unidas por dissolve) —
    # mesma definição de parcela do pipeline, então as cores batem com o funil.
    all_plots = data.load_plot_features().dissolve(by=["site", "plot_id"]).reset_index()
    all_plots = all_plots[all_plots.geometry.notna() & ~all_plots.geometry.is_empty]

    rows = list(all_plots.iterrows())
    cats = [USABILITY.get((r["site"], r["plot_id"]), "gray") for _, r in rows]
    n = {c: cats.count(c) for c in ("green", "red", "gray")}
    groups = {
        "green": folium.FeatureGroup(name=f"{lbl_green} ({n['green']})", show=True),
        "red":   folium.FeatureGroup(name=f"{lbl_red} ({n['red']})", show=True),
        "gray":  folium.FeatureGroup(name=f"{lbl_gray} ({n['gray']})", show=True),
    }

    for (_, row), cat in zip(rows, cats):
        geom = row.geometry
        grp = groups[cat]
        pin_color, poly_color = CAT_STYLE[cat]
        site_short = row["site"].replace("_inventory_plots", "").replace("_inventory", "")
        tooltip = tooltip_tpl.format(site=site_short, plot=row["plot_id"])
        # representative_point() cai SOBRE a geometria (o centroide de um MultiPolygon
        # de partes disjuntas — ex. JAM_A02_2013 — flutuava entre elas).
        p = geom.representative_point()

        # Pin — visível em qualquer zoom
        folium.Marker(
            location=[p.y, p.x],
            icon=folium.Icon(color=pin_color, icon="map-marker", prefix="fa"),
            tooltip=tooltip,
        ).add_to(grp)

        # Geometria — visível ao aproximar. Polígonos viram área preenchida; parcelas
        # de inventário LINEAR (transectos TAP_A01/A04/A05, ver docs/known-issues.md §6)
        # não têm área → desenhadas como linha, em vez de sumirem (antes o .exterior numa
        # LineString estourava e era engolido → pin sem geometria, parecia bug silencioso).
        try:
            gt = geom.geom_type
            if gt in ("Polygon", "MultiPolygon"):
                parts = geom.geoms if gt == "MultiPolygon" else [geom]
                for part in parts:
                    coords = [[c2[1], c2[0]] for c2 in part.exterior.coords]
                    folium.Polygon(
                        locations=coords, color=poly_color, fill=True,
                        fill_opacity=0.5, weight=1.5, tooltip=tooltip,
                    ).add_to(grp)
            elif gt in ("LineString", "MultiLineString"):
                parts = geom.geoms if gt == "MultiLineString" else [geom]
                for part in parts:
                    coords = [[c2[1], c2[0]] for c2 in part.coords]
                    folium.PolyLine(
                        locations=coords, color=poly_color, weight=3,
                        opacity=0.9, tooltip=f"{tooltip} (transecto / sem área)",
                    ).add_to(grp)
        except Exception:
            pass

    for g in groups.values():
        g.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    return m._repr_html_()


_inters_csv = data.ROOT / "data/processed/02_intersections/lidar_inventory_intersections.csv"
_summary_csv = data.ROOT / "data/processed/05_biomass/summary.csv"
_clip_json = data.ROOT / "data/processed/03_clipped_lidar/clip_summary.json"
_cache_key = (data._mtime(_inters_csv) + data._mtime(_summary_csv)
              + data._mtime(_clip_json) + data._src_mtime())
components.html(
    build_map(_cache_key, t("map.layer_tiles"),
              t("map.layer_usable"), t("map.layer_covered_nolabel"),
              t("map.layer_no_lidar"), t("map.tooltip_plot")),
    height=580, scrolling=False,
)
st.caption(t("map.legend_caption"))

with st.expander(t("map.design_note_title")):
    st.markdown(t("map.design_note"))

st.markdown("---")
st.markdown(f"### {t('map.table_title')}")
st.markdown(t("map.table_intro"))

best = data.best_match(data.load_temporal())

# Contagens por site. As parcelas distintas vêm do nome (Name) no KML/CSV.
n_inv = data.inventory_plot_counts()                             # parcelas de inventário
n_tiles = raw.groupby("inventory_file")["laz_file"].nunique()     # tiles LiDAR distintos
n_inter = raw.groupby("inventory_file")["plot_id"].nunique()      # parcelas que cruzam ≥1 tile
n_gap = best.groupby("nome_area_inventario")["plot_id"].nunique()  # idem, pelo melhor match temporal

sites = sorted(set(n_inv.index) | set(n_tiles.index) | set(n_inter.index) | set(n_gap.index))
tab = pd.DataFrame({
    t("map.col_site"): [s.replace("_inventory_plots", "").replace("_inventory", "") for s in sites],
    t("map.col_lidar"): [int(n_tiles.get(s, 0)) for s in sites],
    t("map.col_inventory"): [int(n_inv.get(s, 0)) for s in sites],
    t("map.col_intersection"): [int(n_inter.get(s, 0)) for s in sites],
    t("map.col_intersection_gap"): [int(n_gap.get(s, 0)) for s in sites],
}).sort_values(t("map.col_inventory"), ascending=False)

st.dataframe(tab, hide_index=True, use_container_width=True)
