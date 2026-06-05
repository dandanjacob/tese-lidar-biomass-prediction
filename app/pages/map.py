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

intersected_keys = set(zip(raw["inventory_file"], raw["plot_id"].astype(str)))


@st.cache_data
def build_map(csv_mtime: float, layer_tiles: str, layer_yes: str, layer_no: str, tooltip_tpl: str) -> str:
    # csv_mtime entra só como chave de cache: muda quando o CSV de interseções é
    # regerado, forçando o mapa a recolorir (senão ficaria preso na versão antiga).
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
    # mesma definição de parcela do pipeline, então o vermelho/cinza bate com o CSV.
    all_plots = data.load_plot_features().dissolve(by=["site", "plot_id"]).reset_index()
    all_plots = all_plots[all_plots.geometry.notna() & ~all_plots.geometry.is_empty]

    rows = list(all_plots.iterrows())
    n_yes = sum((r["site"], r["plot_id"]) in intersected_keys for _, r in rows)
    n_no = len(rows) - n_yes
    plot_group_yes = folium.FeatureGroup(name=f"{layer_yes} ({n_yes})", show=True)
    plot_group_no = folium.FeatureGroup(name=f"{layer_no} ({n_no})", show=True)

    for _, row in rows:
        geom = row.geometry
        has = (row["site"], row["plot_id"]) in intersected_keys
        grp = plot_group_yes if has else plot_group_no
        pin_color = "red" if has else "gray"
        poly_color = "#e84545" if has else "#aaaaaa"
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
    plot_group_no.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    return m._repr_html_()


_inters_csv = data.ROOT / "data/processed/02_intersections/lidar_inventory_intersections.csv"
components.html(
    build_map(data._mtime(_inters_csv), t("map.layer_tiles"), t("map.layer_plots_yes"),
              t("map.layer_plots_no"), t("map.tooltip_plot")),
    height=580, scrolling=False,
)

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
