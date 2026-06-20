"""Comparação com a literatura — modelos e projetos de AGB por LiDAR (incl. NASA).

Posiciona os modelos desta tese (AGB por parcela a partir de nuvem LiDAR
aerotransportada do NASA CMS Brazil) frente a estudos publicados de estimativa de
biomassa/carbono por LiDAR aéreo (tropical/Amazônia), produtos espaciais da NASA
(GEDI, CMS) e abordagens de deep learning sobre nuvem de pontos.

⚠️ Os números da literatura foram coletados de fontes primárias por pesquisa
automatizada, mas a verificação adversarial NÃO foi concluída (limite de API). Cada
linha traz o link da fonte — confira o valor no artigo original antes de citar.

Os dados de referência ficam em LIT (editável abaixo); as linhas "Esta tese" são
lidas dos model_metrics_*.json gerados pelo treino.
"""

import pandas as pd
import streamlit as st

from lib import data
from lib.i18n import t

# ── Estudos da literatura (RMSE em Mg/ha, rRMSE em %, R² adimensional) ──────────
# scale: "Parcela" | "Talhão/ha" | "Regional/grade" | "Footprint" | "Grade 1 km"
# sensor: "Aéreo" (ALS) | "Espacial" | "Aéreo+HSI" | "Espacial+inventário"
# verified=False em todos: verificação adversarial não rodou (ver cabeçalho).
LIT = [
    # — Tropical / Amazônia, LiDAR aerotransportado (mais comparável) —
    {"estudo": "Asner & Mascaro 2014", "ano": 2014,
     "regiao": "Tropical (pan-trópico, 4 países)", "sensor": "Aéreo",
     "escala": "Parcela 1 ha", "metodo": "ACD ~ TCH universal (+ área basal, dens. madeira)",
     "n": "804 parcelas", "rmse": None, "rrmse": None, "r2": 0.90,
     "val": "validação cruzada por sítio", "grupo": "Tropical · LiDAR aéreo",
     "fonte": "https://doi.org/10.1016/j.rse.2014.06.023"},
    {"estudo": "Longo et al. 2016", "ano": 2016,
     "regiao": "Amazônia brasileira (intacta + degradada)", "sensor": "Aéreo",
     "escala": "Parcela / ~18.000 ha", "metodo": "ACD ~ métricas LiDAR (regressão)",
     "n": "359 parcelas", "rmse": None, "rrmse": None, "r2": 0.70,
     "val": "explica ~70% da variância", "grupo": "Tropical · LiDAR aéreo",
     "fonte": "https://doi.org/10.1002/2016GB005465"},
    {"estudo": "Bispo et al. 2020 (LiDAR)", "ano": 2020,
     "regiao": "Amazônia brasileira", "sensor": "Aéreo",
     "escala": "Parcela", "metodo": "Métricas LiDAR (apenas)",
     "n": None, "rmse": 67.6, "rrmse": 36.0, "r2": 0.58,
     "val": "—", "grupo": "Tropical · LiDAR aéreo",
     "fonte": "https://doi.org/10.1016/j.rse.2019.111453"},
    {"estudo": "d'Oliveira et al. 2012", "ano": 2012,
     "regiao": "Antimary, Acre (Amazônia ocidental)", "sensor": "Aéreo",
     "escala": "Talhão (1.000 ha)", "metodo": "Métricas LiDAR (floresta manejada)",
     "n": None, "rmse": None, "rrmse": None, "r2": None,
     "val": "—", "grupo": "Tropical · LiDAR aéreo",
     "fonte": "https://doi.org/10.1016/j.rse.2012.05.014"},
    # — NASA espacial: LiDAR a bordo (escala footprint/grade, não parcela) —
    {"estudo": "GEDI L4A (footprint)", "ano": 2022,
     "regiao": "Global — validações por bioma", "sensor": "Espacial",
     "escala": "Footprint ~25 m", "metodo": "OLS sobre métricas RH (modelos por PFT/região)",
     "n": "global", "rmse": None, "rrmse": None, "r2": 0.42,
     "val": "valid. indep.: R²≈0,42 vs ALS (savana); %RMSE 19–71% (EUA temperado) — varia por bioma",
     "grupo": "NASA espacial",
     "fonte": "https://www.sciencedirect.com/science/article/pii/S2666017224000452"},
    {"estudo": "GEDI L4B (grade)", "ano": 2022,
     "regiao": "Global (51,6°S–51,6°N)", "sensor": "Espacial",
     "escala": "Grade 1 km", "metodo": "Inferência híbrida (Ståhl) — modelo + amostragem",
     "n": "—", "rmse": None, "rrmse": None, "r2": None,
     "val": "reporta erro-padrão por célula, não R²/RMSE de regressão",
     "grupo": "NASA espacial",
     "fonte": "https://daac.ornl.gov/GEDI/guides/GEDI_L4B_Gridded_Biomass_V2_1.html"},
    # — Deep learning sobre nuvem de pontos (comparável aos meus PointNet/CNN) —
    {"estudo": "Oehmcke et al. 2024", "ano": 2024,
     "regiao": "Dinamarca (temperado)", "sensor": "Aéreo",
     "escala": "Parcela", "metodo": "Deep NN na nuvem crua (Minkowski CNN > PointNet/KPConv > ABA)",
     "n": None, "rmse": None, "rrmse": None, "r2": None,
     "val": "supera abordagem area-based", "grupo": "Deep learning · nuvem de pontos",
     "fonte": "https://doi.org/10.1016/j.rse.2023.113968"},
]

# Nome amigável de cada modelo desta tese (base key → rótulo curto).
_THESIS_NAMES = {"gbr": "GBR (alturas)", "aba": "ABA (GBR)", "rf": "Random Forest",
                 "pointnet": "PointNet", "raster": "CNN 2D (raster)",
                 "voxel": "CNN 3D (voxel)"}
_BASE_SUFFIXES = ("_gap_noout", "_noout", "_gap", "_ground", "_raw")
# Rótulo curto da configuração (variante) usada na melhor execução de cada modelo.
_VARIANT_SHORT = {
    "full": "solo + ≤1,3 m", "ground_only": "só solo", "raw": "sem proc.",
    "no_outliers": "sem outliers", "gap_corrected": "gap",
    "gap_corrected_noout": "gap + sem outliers",
}


def _base_key(key: str) -> str:
    for s in _BASE_SUFFIXES:
        if key.endswith(s):
            return key[:-len(s)]
    return key


def _thesis_rows():
    """Linhas 'Esta tese' — para cada modelo, a MELHOR execução (maior R²) entre
    todas as variantes (pré-processamento, remoção de outliers, correção de gap),
    com a configuração indicada na coluna Config."""
    order = list(_THESIS_NAMES)
    best = {}
    for m in data.load_models():
        b = _base_key(m.get("key", ""))
        if b not in _THESIS_NAMES:
            continue
        r2 = m.get("cv_global", {}).get("r2")
        if r2 is None:
            continue
        if b not in best or r2 > best[b].get("cv_global", {}).get("r2", -9):
            best[b] = m
    rows = []
    for b in order:
        m = best.get(b)
        if not m:
            continue
        g = m.get("cv_global", {})
        rows.append({
            "estudo": f"Esta tese — {_THESIS_NAMES[b]}", "ano": 2026,
            "regiao": "Amazônia (NASA CMS Brazil)", "sensor": "Aéreo",
            "escala": "Parcela", "metodo": m.get("model", b),
            "config": _VARIANT_SHORT.get(m.get("variant"), m.get("variant", "—")),
            "n": f"{m.get('n_plots', '?')} parcelas",
            "rmse": g.get("rmse"), "rrmse": g.get("rrmse_pct"), "r2": g.get("r2"),
            "val": "k-fold aleatório (5)", "grupo": "Esta tese", "fonte": None,
        })
    return rows


# ── Página ──
st.title(t("benchmarks.title"))
st.caption(t("benchmarks.caption"))
st.warning(t("benchmarks.unverified"))

rows = _thesis_rows() + LIT
df = pd.DataFrame(rows)

# Ordem dos grupos (Esta tese primeiro, depois por proximidade ao trabalho).
GROUP_ORDER = ["Esta tese", "Tropical · LiDAR aéreo",
               "Deep learning · nuvem de pontos", "NASA espacial"]
df["_g"] = df["grupo"].apply(lambda x: GROUP_ORDER.index(x) if x in GROUP_ORDER else 99)
df = df.sort_values(["_g", "ano"]).drop(columns="_g").reset_index(drop=True)

# Síntese — faixas típicas e posicionamento dos resultados da tese.
st.markdown(f"### {t('benchmarks.section_synth')}")
st.markdown(t("benchmarks.synth_body"))

st.markdown(f"### {t('benchmarks.section_table')}")

df["config"] = df["config"].fillna("—")
col_names = {
    "estudo": t("benchmarks.col_study"), "config": t("benchmarks.col_config"),
    "ano": t("benchmarks.col_year"), "regiao": t("benchmarks.col_region"),
    "sensor": t("benchmarks.col_sensor"), "escala": t("benchmarks.col_scale"),
    "metodo": t("benchmarks.col_method"), "n": t("benchmarks.col_n"),
    "rmse": "RMSE", "rrmse": "rRMSE", "r2": "R²",
    "val": t("benchmarks.col_val"), "fonte": t("benchmarks.col_source"),
}
order = ["estudo", "config", "ano", "regiao", "sensor", "escala", "metodo",
         "n", "rmse", "rrmse", "r2", "val", "fonte"]
show = df[order].rename(columns=col_names)

# Cor: gradiente verde→vermelho por métrica (R² maior = melhor; RMSE/rRMSE menor = melhor).
# Células sem valor (literatura não reportou) ficam neutras.
sty = (show.style
       .background_gradient(cmap="RdYlGn", subset=["R²"])
       .background_gradient(cmap="RdYlGn_r", subset=["RMSE", "rRMSE"]))
st.dataframe(
    sty, hide_index=True, use_container_width=True,
    column_config={
        col_names["fonte"]: st.column_config.LinkColumn(
            col_names["fonte"], display_text=t("benchmarks.link_text")),
        "RMSE": st.column_config.NumberColumn("RMSE", format="%.1f",
                                              help=t("benchmarks.help_rmse")),
        "rRMSE": st.column_config.NumberColumn("rRMSE", format="%.1f%%"),
        "R²": st.column_config.NumberColumn("R²", format="%.2f"),
    },
)
st.caption(t("benchmarks.table_caption"))
st.caption(t("benchmarks.compare_highlight"))

# Gráfico RMSE × R² — só estudos com ambos os valores; tese destacada.
plot = df[df["rmse"].notna() & df["r2"].notna()].copy()
if not plot.empty:
    import plotly.express as px
    from lib.theme import C_BLUE, C_RED
    plot["tipo"] = plot["grupo"].apply(
        lambda g: t("benchmarks.legend_thesis") if g == "Esta tese"
        else t("benchmarks.legend_lit"))
    fig = px.scatter(
        plot, x="rmse", y="r2", color="tipo", text="estudo",
        color_discrete_map={t("benchmarks.legend_thesis"): C_RED,
                            t("benchmarks.legend_lit"): C_BLUE},
        labels={"rmse": "RMSE (Mg/ha)", "r2": "R²", "tipo": ""},
        title=t("benchmarks.scatter_title"))
    fig.update_traces(textposition="top center", textfont_size=10,
                      marker=dict(size=11))
    fig.update_layout(height=460, margin=dict(l=0, r=10, t=50, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0,
                                  xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(t("benchmarks.scatter_caption"))

st.markdown("---")
st.markdown(f"#### {t('benchmarks.section_refs')}")
st.markdown(t("benchmarks.refs_note"))
