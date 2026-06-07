"""Modelos de previsão de AGB a partir de LiDAR — abordagem, hiperparâmetros e resultados.

Seleção por botões, em dois grupos: modelos treinados com as **interseções completas**
e modelos treinados com **remoção de outliers** (parcelas de área > 0,5 ha ou
compacidade < 0,6 retiradas). A tabela de comparação no topo é comum aos dois grupos.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import data
from lib.i18n import md, t, with_acronyms
from lib.theme import C_BLUE, C_RED

# Ordem canônica de exibição (por modelo, dentro de cada grupo de variante).
ORDER = ["gbr", "aba", "rf", "pointnet", "raster", "voxel"]


def _base_key(m):
    return m["key"][:-6] if m["key"].endswith("_noout") else m["key"]


def _ord(m):
    b = _base_key(m)
    return ORDER.index(b) if b in ORDER else len(ORDER)


def _variant_label(m):
    return (t("models.variant_noout") if m.get("variant") == "no_outliers"
            else t("models.variant_full"))


def render_detail(m):
    """Bloco de detalhe de um modelo: abordagem, métricas, hiperparâmetros, CV."""
    if m.get("approach_key"):
        st.markdown(with_acronyms(md(m["approach_key"])), unsafe_allow_html=True)
    st.caption(f"{_variant_label(m)}"
               + (f" · {t('models.trained_at')}: {m['trained_at']}"
                  if m.get("trained_at") else ""))

    c = st.columns(5)
    c[0].metric(t("models.m_library"), m.get("library", "—"))
    c[1].metric(t("models.m_plots"), m.get("n_plots", "—"))
    c[2].metric(t("models.m_sites"), m.get("n_sites", "—"))
    c[3].metric(t("models.m_features"), str(m.get("n_features", "—")))
    c[4].metric(t("models.m_agb"), f"{m.get('agb_mean', '—')} ± {m.get('agb_std', '')}")

    if m.get("hyperparameters"):
        st.markdown(f"#### {t('models.section_hyper')}")
        hp = pd.DataFrame([{t("models.hp_param"): k, t("models.hp_value"): str(v)}
                           for k, v in m["hyperparameters"].items()])
        st.table(hp)

    st.markdown(f"#### {t('models.section_results')}")
    g = m.get("cv_global", {})
    if g:
        cc = st.columns(3)
        cc[0].metric(t("models.cv_rmse"), f"{g.get('rmse', '—')} Mg/ha",
                     help=t("models.cv_help_global"))
        cc[1].metric(t("models.cv_r2"), f"{g.get('r2', '—')}", help=t("models.cv_help_r2"))
        cc[2].metric(t("models.cv_rrmse"), f"{g.get('rrmse_pct', '—')}%")
    sm = m.get("cv_fold_mean", {})
    if sm:
        st.caption(f"{t('models.fold_mean')}: RMSE {sm.get('rmse')} · "
                   f"R² {sm.get('r2')} · rRMSE {sm.get('rrmse_pct')}%")

    cv = data.load_cv_results(m.get("cv_file", "cv_results.csv"))
    if not cv.empty and "fold" in cv.columns:
        cvd = cv.copy()
        cvd["fold_label"] = t("models.col_fold") + " " + cvd["fold"].astype(str)
        cvd["grupo"] = cvd["r2"].apply(
            lambda v: t("models.r2_pos") if pd.notna(v) and v > 0 else t("models.r2_neg"))
        fig = px.bar(
            cvd.sort_values("fold"), x="rmse", y="fold_label", orientation="h",
            color="grupo",
            color_discrete_map={t("models.r2_pos"): C_BLUE, t("models.r2_neg"): C_RED},
            labels={"rmse": t("models.col_rmse"), "fold_label": "", "grupo": ""},
            title=t("models.chart_rmse_title"))
        fig.update_layout(height=max(300, len(cvd) * 34 + 130),
                          margin=dict(l=0, r=10, t=50, b=10),
                          legend=dict(orientation="h", yanchor="bottom", y=1.0,
                                      xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{m['key']}")

        show = cvd[["fold", "n_test", "rmse", "r2", "rrmse_pct"]].rename(columns={
            "fold": t("models.col_fold"), "n_test": t("models.col_n"),
            "rmse": t("models.col_rmse"), "r2": t("models.col_r2"),
            "rrmse_pct": t("models.col_rrmse")})
        st.dataframe(show, hide_index=True, use_container_width=True)

    # Importância das variáveis — só os modelos interpretáveis (ABA) trazem isto.
    fi = m.get("feature_importance")
    if fi:
        st.markdown(f"#### {t('models.section_importance')}")
        top = pd.DataFrame(fi[:15]).sort_values("importance")
        fig_i = px.bar(
            top, x="importance", y="feature", orientation="h",
            labels={"importance": t("models.col_importance"), "feature": ""},
            title=t("models.section_importance"))
        fig_i.update_traces(marker_color=C_BLUE)
        fig_i.update_layout(height=max(360, len(top) * 26 + 130),
                            margin=dict(l=0, r=10, t=50, b=10))
        st.plotly_chart(fig_i, use_container_width=True, key=f"imp_{m['key']}")
        st.caption(t("models.importance_caption"))


# ── Página ──
st.title(t("models.title"))
st.caption(with_acronyms(t("models.caption")), unsafe_allow_html=True)

models = data.load_models()
if not models:
    st.warning(t("models.no_data"))
    st.stop()

models = sorted(models, key=_ord)
full = [m for m in models if m.get("variant") != "no_outliers"]
noout = [m for m in models if m.get("variant") == "no_outliers"]

st.markdown(t("models.intro"))

# ── Comparação global (uma linha por modelo; inclui os sem outliers) ──
if len(models) > 1:
    st.markdown(f"### {t('models.section_compare')}")
    comp = pd.DataFrame([{
        t("models.col_model"): m.get("name", m.get("model", m["key"])),
        t("models.col_variant"): _variant_label(m),
        t("models.m_plots"): m.get("n_plots", "—"),
        t("models.cv_rmse"): m.get("cv_global", {}).get("rmse", "—"),
        t("models.cv_r2"): m.get("cv_global", {}).get("r2", "—"),
        t("models.cv_rrmse"): m.get("cv_global", {}).get("rrmse_pct", "—"),
    } for m in (full + noout)])
    st.table(comp)
    st.caption(t("models.compare_caption"))

# ── Seletor por botões, agrupado por variante ──
st.markdown(f"### {t('models.section_choose')}")
if "models_sel" not in st.session_state or \
        st.session_state.models_sel not in {m["key"] for m in models}:
    st.session_state.models_sel = (full or models)[0]["key"]

clicked = None


def _group(label, group):
    global clicked
    if not group:
        return
    st.markdown(f"**{label}**")
    cols = st.columns(len(group))
    for col, m in zip(cols, group):
        sel = st.session_state.models_sel == m["key"]
        if col.button(m.get("name", m["key"]), key=f"btn_{m['key']}",
                      type="primary" if sel else "secondary",
                      use_container_width=True):
            clicked = m["key"]


_group(t("models.variant_full"), full)
if noout:
    _group(t("models.variant_noout"), noout)
else:
    st.caption(t("models.noout_pending"))

if clicked and clicked != st.session_state.models_sel:
    st.session_state.models_sel = clicked
    st.rerun()

sel = next((m for m in models if m["key"] == st.session_state.models_sel), models[0])

st.markdown("---")
render_detail(sel)

st.markdown("---")
st.markdown(t("models.results_desc"))
