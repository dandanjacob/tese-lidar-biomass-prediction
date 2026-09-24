"""
Dashboard — LiDAR Biomass Prediction

Ponto de entrada do app. Configura a página, o seletor de idioma e a navegação
entre páginas (cada página vive em app/pages/), agrupada por estágio do trabalho:
Enquadramento → Artigo → Dados & Método → Modelagem → Apêndice. Todo o texto da
interface é editável em app/locales/<idioma>.json.

Rodar:  bash app/run.sh   ·   make app
"""

import streamlit as st

from lib.i18n import enable_live_reload, language_selector_top, t
from lib.theme import page_config

page_config()
enable_live_reload()  # recarrega o navegador ao salvar locales/*.json
language_selector_top()

st.sidebar.caption(t("common.sidebar_caption"))
st.sidebar.markdown("---")

# Navegação agrupada por estágio — st.navigation aceita {seção: [páginas]} nativamente
# e renderiza um cabeçalho por grupo na sidebar, em vez de uma lista plana.
nav = {
    t("nav.section_framing"): [
        st.Page("pages/home.py", title=t("nav.home"), icon="🏠", default=True),
        st.Page("pages/cronograma.py", title=t("nav.cronograma"), icon="🗓️"),
    ],
    t("nav.section_article"): [
        st.Page("pages/artigo.py", title=t("nav.artigo"), icon="📄"),
    ],
    t("nav.section_data"): [
        st.Page("pages/map.py", title=t("nav.map"), icon="🗺️"),
        st.Page("pages/intersections.py", title=t("nav.intersections"), icon="📊"),
        st.Page("pages/geometry.py", title=t("nav.geometry"), icon="📐"),
        st.Page("pages/outliers.py", title=t("nav.outliers"), icon="🔍"),
        st.Page("pages/pointcloud.py", title=t("nav.pointcloud"), icon="☁️"),
        st.Page("pages/biomass.py", title=t("nav.biomass"), icon="🌿"),
    ],
    t("nav.section_modeling"): [
        st.Page("pages/models.py", title=t("nav.models"), icon="🤖"),
        st.Page("pages/benchmarks.py", title=t("nav.benchmarks"), icon="📚"),
    ],
    t("nav.section_appendix"): [
        st.Page("pages/qualidade_dados.py", title=t("nav.qualidade"), icon="🧪"),
    ],
}
st.navigation(nav).run()

# Rodapé global — aparece ao fim de qualquer página (main.py roda a cada navegação).
st.markdown("---")
st.markdown(t("common.footer"), unsafe_allow_html=True)
