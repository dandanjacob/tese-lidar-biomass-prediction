"""Paleta de cores e configuração de página compartilhadas."""

import streamlit as st

from lib.i18n import t

C_BLUE = "#4a90d9"
C_RED = "#e84545"
C_LIGHT = "#a8d4f5"
C_PINK = "#f5a8a8"


def page_config():
    st.set_page_config(page_title=t("common.page_title"), page_icon="🌳", layout="wide")
