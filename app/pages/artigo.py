"""Artigo completo — versão de leitura contínua da dissertação, com figuras reais
geradas a partir dos mesmos dados que alimentam as páginas exploratórias do app.

Ao contrário das demais páginas (feitas para explorar um recorte do pipeline por vez),
esta é pensada para ser lida do início ao fim, como um artigo: resumo → introdução →
dados & método → resultados → discussão → referências.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from lib import charts, data
from lib.i18n import md, t, with_acronyms
from lib.theme import C_AMBER, C_CANOPY, C_LIDAR, C_RUST

st.title(t("artigo.title"))
st.markdown(f"##### {t('artigo.subtitle')}")
st.caption(t("artigo.byline"))
st.markdown("---")

tab_resumo, tab_intro, tab_dados, tab_resultados, tab_discussao, tab_refs = st.tabs([
    t("artigo.tab_resumo"), t("artigo.tab_intro"), t("artigo.tab_dados"),
    t("artigo.tab_resultados"), t("artigo.tab_discussao"), t("artigo.tab_referencias"),
])

# ── Resumo ────────────────────────────────────────────────────────────────────
with tab_resumo:
    st.markdown(with_acronyms(md("artigo_resumo")), unsafe_allow_html=True)

# ── Introdução ────────────────────────────────────────────────────────────────
with tab_intro:
    st.markdown(with_acronyms(md("artigo_intro")), unsafe_allow_html=True)

# ── Dados & Método ────────────────────────────────────────────────────────────
with tab_dados:
    st.markdown(with_acronyms(md("artigo_dados_1")), unsafe_allow_html=True)
    components.html(charts.pipeline_flow_html(t("home.pipeline_steps")), height=520)
    st.caption(
        "**Figura 1** — Pipeline de dados: dois ramos independentes (LiDAR bruto; "
        "inventário de campo) convergem no cruzamento espacial e clipping, e "
        "alimentam o treino do modelo junto com a biomassa de referência."
    )
    st.markdown(with_acronyms(md("artigo_dados_2")), unsafe_allow_html=True)

# ── Resultados ────────────────────────────────────────────────────────────────
with tab_resultados:
    st.markdown(with_acronyms(md("artigo_resultados_1")), unsafe_allow_html=True)

    # Tabela 1 — comparação completa modelo × variante de pré-processamento.
    _NAMES = {"gbr": "GBR — alturas ordenadas", "aba": "ABA (GBR estrutural)",
              "rf": "Random Forest (estrutural)", "pointnet": "PointNet (nuvem crua)",
              "raster": "CNN 2D (raster)", "voxel": "CNN 3D (voxel)"}
    # Ordem do mais específico pro menos específico — "_noout_raw"/"_gap_raw" (ablação
    # ISOLADA: só esse tratamento, nuvem crua, sem empilhar) precisam casar ANTES de
    # "_raw" sozinho, senão o strip errado deixa "_noout"/"_gap" grudado na base e a
    # linha some da tabela (mesmo bug já corrigido em app/pages/models.py).
    _SUFFIXES = ("_gap_noout", "_noout_raw", "_gap_raw", "_noout", "_gap",
                "_filteronly", "_ground", "_raw")
    _VARIANT_LABEL = {"raw": "Cru (sem processamento)", "ground_only": "Só solo",
                       "filter_only": "Só filtro ≤1,3 m", "full": "Solo + filtro",
                       "outliers_only": "Só outliers", "gap_only": "Só gap temporal",
                       "no_outliers": "Solo+filtro+outliers",
                       "gap_corrected_noout": "Tudo combinado",
                       "gap_corrected": "Solo+filtro+gap"}
    _VARIANT_RANK = {"raw": 0, "ground_only": 1, "filter_only": 2, "full": 3,
                      "outliers_only": 4, "gap_only": 5, "no_outliers": 6,
                      "gap_corrected": 7, "gap_corrected_noout": 8}

    def _base(key):
        for suf in _SUFFIXES:
            if key.endswith(suf):
                return key[:-len(suf)]
        return key

    rows = []
    for m in data.load_models():
        b = _base(m.get("key", ""))
        if b not in _NAMES:
            continue
        g = m.get("cv_global", {})
        if g.get("r2") is None:
            continue
        rows.append({
            "Modelo": _NAMES[b], "Variante": _VARIANT_LABEL.get(m.get("variant"), m.get("variant")),
            "_rank": _VARIANT_RANK.get(m.get("variant"), 9),
            "n": m.get("n_plots"), "RMSE": g.get("rmse"), "R²": g.get("r2"),
            "rRMSE": g.get("rrmse_pct"),
        })
    tbl1 = pd.DataFrame(rows).sort_values(["_rank", "Modelo"]).drop(columns="_rank")
    sty1 = (tbl1.style.hide(axis="index")
            .format({"RMSE": "{:.1f}", "R²": "{:.3f}", "rRMSE": "{:.1f}%"})
            .background_gradient(cmap="RdYlGn", subset=["R²"])
            .background_gradient(cmap="RdYlGn_r", subset=["RMSE", "rRMSE"]))
    st.dataframe(sty1, hide_index=True, use_container_width=True, height=460)
    st.caption(
        "**Tabela 1** — RMSE (Mg/ha), R² e rRMSE (%) de validação cruzada k-fold "
        "global, por modelo e variante de pré-processamento (Seção 2.6). "
        "'Só X' são tratamentos ISOLADOS (nuvem crua, só esse tratamento ligado, "
        "sem empilhar com os demais); 'Solo+filtro', 'Solo+filtro+outliers' e "
        "'Tudo combinado' empilham os tratamentos anteriores em cima um do outro."
    )

    st.markdown(with_acronyms(md("artigo_resultados_2")), unsafe_allow_html=True)

    # Figura 2 — predito x observado do melhor modelo (raster, gap+noout).
    oof = data.load_model_oof("cv_results_raster_gap_noout.csv")
    if oof and oof.get("y_true"):
        odf = pd.DataFrame({"obs": oof["y_true"], "pred": oof["y_pred"]})
        mx = max(odf["obs"].max(), odf["pred"].max()) * 1.05
        fig2 = px.scatter(odf, x="obs", y="pred", opacity=0.6,
                           labels={"obs": "AGB observada (Mg/ha)", "pred": "AGB prevista (Mg/ha)"},
                           title="Predito × observado — CNN 2D (raster), gap + sem outliers")
        fig2.add_shape(type="line", x0=0, y0=0, x1=mx, y1=mx,
                        line=dict(dash="dash", color="gray", width=1))
        fig2.update_traces(marker_color=C_CANOPY)
        fig2.update_xaxes(range=[0, mx]); fig2.update_yaxes(range=[0, mx])
        fig2.update_layout(height=440, margin=dict(l=0, r=10, t=50, b=10))
        st.plotly_chart(fig2, use_container_width=True)
        st.caption(
            "**Figura 2** — Cada ponto é uma parcela (previsão *out-of-fold*); a "
            "linha tracejada é a identidade (predito = observado). Dispersão maior "
            "nas parcelas de AGB mais alta é o padrão típico de um modelo com "
            "R² moderado."
        )

    # Figura 3 — ablação de dimensionalidade (GBR: K quantis vs. vetor completo).
    dimred_pts = []
    for m in data.load_models():
        k = m.get("key", "")
        if k.startswith("gbrh") and k.endswith("_noout"):
            kq = int(k[len("gbrh"):-len("_noout")])
            r2 = m.get("cv_global", {}).get("r2")
            if r2 is not None:
                dimred_pts.append({"K": kq, "R²": r2, "grupo": "Quantis de altura (K)"})
    full_m = next((m for m in data.load_models()
                    if m.get("key") == "gbr_noout" and m.get("variant") == "no_outliers"), None)
    ddf = pd.DataFrame(sorted(dimred_pts, key=lambda r: r["K"]))
    if not ddf.empty:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=ddf["K"], y=ddf["R²"], mode="lines+markers", name="GBR sobre K quantis",
            line=dict(color=C_CANOPY, width=2.5), marker=dict(size=9)))
        if full_m:
            r2_full = full_m.get("cv_global", {}).get("r2")
            fig3.add_hline(y=r2_full, line_dash="dash", line_color=C_RUST,
                            annotation_text=f"Vetor completo (1024 alturas) · R²={r2_full:.2f}",
                            annotation_position="bottom right")
        fig3.update_layout(
            title="R² de validação cruzada vs. número de quantis de altura (K)",
            xaxis_title="K (quantis de altura, escala log)", yaxis_title="R² (CV global)",
            xaxis_type="log", height=420, margin=dict(l=0, r=10, t=50, b=10))
        st.plotly_chart(fig3, use_container_width=True)
        st.caption(
            "**Figura 3** — Todos os pontos usam a variante *sem outliers* (n=325). "
            "A linha tracejada vermelha marca o desempenho do vetor de 1024 alturas "
            "ordenadas — superado já pela representação de 8 quantis."
        )

    st.markdown(with_acronyms(md("artigo_resultados_3")), unsafe_allow_html=True)

    # Figura 4 — importância de variáveis, modelo ABA (gap+noout).
    _aba = next((m for m in data.load_models() if m.get("key") == "aba_gap_noout"), None)
    if _aba:
        fi = _aba.get("feature_importance") or []
        if fi:
            top = pd.DataFrame(sorted(fi, key=lambda r: -r["importance"])[:10])
            fig4 = px.bar(top.sort_values("importance"), x="importance", y="feature",
                          orientation="h",
                          labels={"importance": "Importância (Gini)", "feature": ""},
                          title="Importância de variáveis — modelo ABA (top 10)")
            fig4.update_traces(marker_color=C_LIDAR)
            fig4.update_layout(height=380, margin=dict(l=0, r=10, t=50, b=10))
            st.plotly_chart(fig4, use_container_width=True)
            st.caption(
                "**Figura 4** — Percentis de altura do dossel (p05, p75, p50, p10, "
                "p25) concentram a maior parte da importância; `vfd_entropy` "
                "(entropia da densidade vertical) e `lap_roughness` (rugosidade "
                "convolucional do CHM) carregam sinal estrutural complementar."
            )

    st.markdown(with_acronyms(md("artigo_resultados_4")), unsafe_allow_html=True)

# ── Discussão ─────────────────────────────────────────────────────────────────
with tab_discussao:
    st.markdown(with_acronyms(md("artigo_discussao")), unsafe_allow_html=True)

# ── Referências ───────────────────────────────────────────────────────────────
with tab_refs:
    st.markdown(with_acronyms(md("artigo_referencias")), unsafe_allow_html=True)
