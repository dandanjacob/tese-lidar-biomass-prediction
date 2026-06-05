"""
Dashboard — LiDAR Biomass Prediction

Ponto de entrada do app. Configura a página, o seletor de idioma e a navegação
entre páginas (cada página vive em app/pages/). Todo o texto da interface é
editável em app/locales/<idioma>.json.

Rodar:  bash app/run.sh   ·   make app
"""

import streamlit as st

from lib.i18n import t, language_selector, enable_live_reload
from lib.theme import page_config

page_config()
enable_live_reload()  # recarrega o navegador ao salvar locales/*.json
language_selector()
st.sidebar.markdown("---")
st.sidebar.caption(t("common.sidebar_caption"))

# Navegação — os títulos vêm do JSON, então mudam de idioma automaticamente.
pages = [
    st.Page("pages/home.py", title=t("nav.home"), icon="🏠", default=True),
    st.Page("pages/cronograma.py", title=t("nav.cronograma"), icon="🗓️"),
    st.Page("pages/map.py", title=t("nav.map"), icon="🗺️"),
    st.Page("pages/intersections.py", title=t("nav.intersections"), icon="📊"),
    st.Page("pages/geometry.py", title=t("nav.geometry"), icon="📐"),
    st.Page("pages/pointcloud.py", title=t("nav.pointcloud"), icon="☁️"),
    st.Page("pages/biomass.py", title=t("nav.biomass"), icon="🌿"),
    st.Page("pages/models.py", title=t("nav.models"), icon="🤖"),
]
st.navigation(pages).run()

# Rodapé global — aparece ao fim de qualquer página (main.py roda a cada navegação).
st.markdown("---")
st.markdown(t("common.footer"), unsafe_allow_html=True)